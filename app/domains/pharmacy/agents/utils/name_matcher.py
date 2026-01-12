"""
LLM-based Name Matcher for Pharmacy Customer Validation.

Uses LLM for fuzzy name matching with high accuracy to validate
user-provided names against PLEX customer records.

Handles:
- Accents and special characters (José = Jose)
- Name order variations (JUAN PEREZ = PEREZ JUAN)
- Common typos and misspellings (Gonzalez = Gonzales)
- Abbreviations (MARIA = MA., JUAN CARLOS = J CARLOS)
- Partial names (MARIA vs MARIA JOSE)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.integrations.llm import ModelComplexity, get_llm_for_task

logger = logging.getLogger(__name__)


@dataclass
class NameMatchResult:
    """Result of LLM name comparison."""

    is_match: bool
    score: float  # 0.0 - 1.0
    explanation: str
    normalized_provided: str
    normalized_expected: str


class LLMNameMatcher:
    """
    Uses LLM for fuzzy name matching with high accuracy.

    Designed for Spanish/Argentine names with support for:
    - Accent-insensitive matching
    - Name order flexibility
    - Typo tolerance
    - Abbreviation recognition
    """

    # Threshold for considering a match
    MATCH_THRESHOLD = 0.75

    # YAML template path (relative to prompts/templates)
    TEMPLATE_FILE = "pharmacy/name_matcher.yaml"

    # Fallback prompt if template not found
    FALLBACK_PROMPT = """Eres un experto en comparación de nombres en español argentino.
Tu tarea es determinar si dos nombres corresponden a la MISMA PERSONA.

Considera:
- Acentos y tildes son equivalentes (José = Jose)
- El orden puede variar (JUAN PEREZ = PEREZ JUAN)
- Abreviaturas son válidas (MARIA = MA., JUAN CARLOS = J CARLOS)
- Nombres parciales pueden coincidir (JUAN = JUAN CARLOS)
- Typos comunes (Gonzalez = Gonzales)

Nombre proporcionado: "{provided_name}"
Nombre en base de datos: "{expected_name}"

Responde ÚNICAMENTE en JSON válido:
{{"is_match": true/false, "score": 0.0-1.0, "explanation": "breve explicación"}}"""

    def __init__(self, templates_dir: Path | str | None = None):
        """
        Initialize the name matcher.

        Args:
            templates_dir: Path to prompts/templates directory
        """
        if templates_dir is None:
            # Default to app/prompts/templates
            self._templates_dir = Path(__file__).parents[4] / "prompts" / "templates"
        else:
            self._templates_dir = Path(templates_dir)

        self._prompt_template: str | None = None
        self._loaded = False

    async def _ensure_loaded(self) -> None:
        """Lazy load YAML template on first use."""
        if self._loaded:
            return

        path = self._templates_dir / self.TEMPLATE_FILE
        try:
            content = await asyncio.to_thread(path.read_text, encoding="utf-8")
            data = yaml.safe_load(content)
            if not isinstance(data, dict):
                logger.warning(f"Invalid template format in {path}, expected dict")
                self._loaded = True
                return
            prompts = data.get("prompts", [])
            if prompts:
                self._prompt_template = prompts[0].get("template", "")
            logger.debug(f"Loaded name matcher template from {path}")
        except Exception as e:
            logger.warning(f"Failed to load name matcher template: {e}, using fallback")
            self._prompt_template = None

        self._loaded = True

    async def compare(self, provided_name: str, expected_name: str) -> NameMatchResult:
        """
        Compare provided name against expected name using LLM.

        Args:
            provided_name: Name provided by user
            expected_name: Name from PLEX record

        Returns:
            NameMatchResult with match decision and confidence
        """
        # Normalize names for comparison
        normalized_provided = self._normalize_name(provided_name)
        normalized_expected = self._normalize_name(expected_name)

        # Quick exact match check
        if normalized_provided == normalized_expected:
            return NameMatchResult(
                is_match=True,
                score=1.0,
                explanation="Coincidencia exacta",
                normalized_provided=normalized_provided,
                normalized_expected=normalized_expected,
            )

        # Use LLM for fuzzy matching
        try:
            result = await self._llm_compare(provided_name, expected_name)
            result.normalized_provided = normalized_provided
            result.normalized_expected = normalized_expected
            return result
        except Exception as e:
            logger.error(f"LLM name comparison failed: {e}")
            # Fallback to simple comparison
            return self._fallback_compare(
                normalized_provided,
                normalized_expected,
            )

    async def find_best_match(
        self,
        provided_name: str,
        candidates: list[dict],
        name_field: str = "nombre",
    ) -> tuple[dict | None, float]:
        """
        Find best matching candidate from list.

        Args:
            provided_name: Name provided by user
            candidates: List of PLEX customer dicts
            name_field: Field name containing the name to compare

        Returns:
            Tuple of (best_match_customer, score) or (None, 0) if no match
        """
        best_match = None
        best_score = 0.0

        for candidate in candidates:
            candidate_name = candidate.get(name_field, "")
            if not candidate_name:
                continue

            result = await self.compare(provided_name, candidate_name)

            if result.score > best_score:
                best_score = result.score
                best_match = candidate

            # Early exit if perfect match
            if result.score >= 0.95:
                break

        if best_score >= self.MATCH_THRESHOLD:
            logger.info(f"Best name match found: score={best_score:.2f}")
            return best_match, best_score

        logger.info(f"No match above threshold: best_score={best_score:.2f}")
        return None, 0.0

    async def _llm_compare(
        self,
        provided_name: str,
        expected_name: str,
    ) -> NameMatchResult:
        """
        Use LLM for name comparison.

        Args:
            provided_name: Name provided by user
            expected_name: Name from PLEX record

        Returns:
            NameMatchResult from LLM analysis
        """
        # Ensure template is loaded
        await self._ensure_loaded()

        # Build prompt from template or fallback
        template = self._prompt_template or self.FALLBACK_PROMPT
        prompt = template.format(
            provided_name=provided_name.upper(),
            expected_name=expected_name.upper(),
        )

        # Get LLM with low temperature for consistent results
        llm = get_llm_for_task(complexity=ModelComplexity.SIMPLE, temperature=0.1)
        response = await llm.ainvoke(prompt)

        # Extract content - handle both str and list types
        raw_content = response.content if hasattr(response, "content") else str(response)
        if isinstance(raw_content, list):
            content = " ".join(str(item) for item in raw_content)
        else:
            content = str(raw_content)

        return self._parse_llm_response(content, provided_name, expected_name)

    def _parse_llm_response(
        self,
        content: str,
        provided_name: str,
        expected_name: str,
    ) -> NameMatchResult:
        """
        Parse LLM response into NameMatchResult.

        Args:
            content: Raw LLM response
            provided_name: Original provided name
            expected_name: Original expected name

        Returns:
            Parsed NameMatchResult
        """
        try:
            # Extract JSON from response
            json_match = re.search(r"\{[^}]+\}", content, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON found in response")

            data = json.loads(json_match.group())

            is_match = data.get("is_match", False)
            score = float(data.get("score", 0.0))
            explanation = data.get("explanation", "")

            # Validate score range
            score = max(0.0, min(1.0, score))

            # Ensure is_match is consistent with score
            if score >= self.MATCH_THRESHOLD and not is_match:
                is_match = True
            elif score < self.MATCH_THRESHOLD and is_match:
                is_match = False

            return NameMatchResult(
                is_match=is_match,
                score=score,
                explanation=explanation,
                normalized_provided=self._normalize_name(provided_name),
                normalized_expected=self._normalize_name(expected_name),
            )

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            # Fallback to simple comparison
            return self._fallback_compare(
                self._normalize_name(provided_name),
                self._normalize_name(expected_name),
            )

    def _normalize_name(self, name: str) -> str:
        """
        Normalize name for comparison.

        - Uppercase
        - Remove accents
        - Trim whitespace
        - Collapse multiple spaces

        Args:
            name: Name to normalize

        Returns:
            Normalized name string
        """
        if not name:
            return ""

        # Uppercase
        name = name.upper()

        # Remove accents
        name = unicodedata.normalize("NFD", name)
        name = "".join(c for c in name if unicodedata.category(c) != "Mn")

        # Remove extra whitespace
        name = " ".join(name.split())

        return name.strip()

    def _fallback_compare(
        self,
        normalized_provided: str,
        normalized_expected: str,
    ) -> NameMatchResult:
        """
        Fallback comparison when LLM is unavailable.

        Uses simple token-based comparison.

        Args:
            normalized_provided: Normalized provided name
            normalized_expected: Normalized expected name

        Returns:
            NameMatchResult from simple comparison
        """
        if not normalized_provided or not normalized_expected:
            return NameMatchResult(
                is_match=False,
                score=0.0,
                explanation="Nombre vacío",
                normalized_provided=normalized_provided,
                normalized_expected=normalized_expected,
            )

        # Exact match
        if normalized_provided == normalized_expected:
            return NameMatchResult(
                is_match=True,
                score=1.0,
                explanation="Coincidencia exacta",
                normalized_provided=normalized_provided,
                normalized_expected=normalized_expected,
            )

        # Token-based comparison
        provided_tokens = set(normalized_provided.split())
        expected_tokens = set(normalized_expected.split())

        if not provided_tokens or not expected_tokens:
            return NameMatchResult(
                is_match=False,
                score=0.0,
                explanation="No se pueden comparar nombres",
                normalized_provided=normalized_provided,
                normalized_expected=normalized_expected,
            )

        # Calculate overlap
        common = provided_tokens & expected_tokens
        total = provided_tokens | expected_tokens

        score = len(common) / len(total) if total else 0.0

        # Boost score if all provided tokens match
        if provided_tokens <= expected_tokens:
            score = min(1.0, score + 0.2)

        is_match = score >= self.MATCH_THRESHOLD

        return NameMatchResult(
            is_match=is_match,
            score=score,
            explanation=f"Coincidencia de tokens: {len(common)}/{len(total)}",
            normalized_provided=normalized_provided,
            normalized_expected=normalized_expected,
        )


__all__ = ["LLMNameMatcher", "NameMatchResult"]
