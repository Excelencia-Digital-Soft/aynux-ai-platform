"""
Hybrid Name Matcher for Pharmacy Customer Validation.

Uses deterministic algorithms (rapidfuzz) first with LLM fallback for ambiguous cases.
This optimizes for performance (<50ms deterministic) while maintaining accuracy
for complex Spanish name patterns.

Thresholds:
- >85%: Match (deterministic only)
- 65-85%: Ambiguous (LLM fallback)
- <65%: No match (deterministic only)

Expected LLM Fallback Rate:
- ~85% of comparisons avoid LLM calls
- ~15% use LLM for ambiguous cases (65-85% score)
"""

from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from rapidfuzz import fuzz

from app.domains.pharmacy.agents.utils.name_matcher import LLMNameMatcher

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class NameMatchResult:
    """Result of name comparison."""

    is_match: bool
    score: float  # 0.0 - 1.0
    explanation: str
    normalized_provided: str
    normalized_expected: str
    method: str = "unknown"  # "exact", "deterministic", "llm", "fallback"


class HybridNameMatcher:
    """
    Hybrid name matcher: deterministic first, LLM fallback for ambiguous cases.

    Optimized for Spanish/Argentine names with support for:
    - Accent-insensitive matching
    - Name order flexibility (JUAN PEREZ = PEREZ JUAN)
    - Common abbreviations (MA. = MARIA, J CARLOS = JUAN CARLOS)
    - Partial name matching (JUAN vs JUAN CARLOS)
    - Typo tolerance (Gonzalez = Gonzales)

    Performance targets:
    - Deterministic: <50ms (typically ~5ms)
    - LLM fallback: ~500-1500ms (only for ambiguous cases)
    """

    # Threshold configuration
    MATCH_THRESHOLD = 0.85  # Above this = definite match (deterministic)
    AMBIGUOUS_THRESHOLD = 0.65  # Below this = definite no-match (deterministic)
    FINAL_MATCH_THRESHOLD = 0.75  # Used in find_best_match

    # Spanish name abbreviations (language conventions, not business logic)
    # These are common Argentine Spanish name abbreviations
    ABBREVIATIONS: dict[str, str] = {
        # Single token abbreviations
        "MA": "MARIA",
        "MA.": "MARIA",
        "J": "JUAN",
        "J.": "JUAN",
        "FCO": "FRANCISCO",
        "FCO.": "FRANCISCO",
        "ANT": "ANTONIO",
        "ANT.": "ANTONIO",
        "CARO": "CAROLINA",
        "GUILLE": "GUILLERMO",
        "GONZA": "GONZALO",
        "FLOR": "FLORENCIA",
        "NICO": "NICOLAS",
        "MATI": "MATIAS",
        "AGUS": "AGUSTIN",
        "SEBA": "SEBASTIAN",
        # Two-token compound name abbreviations
        "JC": "JUAN CARLOS",
        "J CARLOS": "JUAN CARLOS",
        "J. CARLOS": "JUAN CARLOS",
        "MA JOSE": "MARIA JOSE",
        "M JOSE": "MARIA JOSE",
    }

    def __init__(self, llm_matcher: LLMNameMatcher | None = None):
        """
        Initialize hybrid name matcher.

        Args:
            llm_matcher: Optional LLMNameMatcher instance for fallback.
                        If None, creates a new instance on first use.
        """
        self._llm_matcher = llm_matcher

    def _get_llm_matcher(self) -> LLMNameMatcher:
        """Get or create LLM matcher for fallback."""
        if self._llm_matcher is None:
            self._llm_matcher = LLMNameMatcher()
        return self._llm_matcher

    async def compare(
        self,
        provided_name: str,
        expected_name: str,
    ) -> NameMatchResult:
        """
        Compare provided name against expected name.

        Uses deterministic matching first, LLM fallback for ambiguous cases.

        Args:
            provided_name: Name provided by user
            expected_name: Name from PLEX record

        Returns:
            NameMatchResult with match decision, confidence, and method used
        """
        # 1. Normalize names
        norm_provided = self._normalize_name(provided_name)
        norm_expected = self._normalize_name(expected_name)

        # 2. Exact match (fast path)
        if norm_provided == norm_expected:
            return NameMatchResult(
                is_match=True,
                score=1.0,
                explanation="Coincidencia exacta",
                normalized_provided=norm_provided,
                normalized_expected=norm_expected,
                method="exact",
            )

        # 3. Deterministic matching with rapidfuzz
        score = self._deterministic_score(norm_provided, norm_expected)

        logger.debug(f"Deterministic score: {score:.2f} " f"(provided='{norm_provided}', expected='{norm_expected}')")

        # 4. Decision based on thresholds
        if score >= self.MATCH_THRESHOLD:
            return NameMatchResult(
                is_match=True,
                score=score,
                explanation=f"Coincidencia alta ({score:.0%})",
                normalized_provided=norm_provided,
                normalized_expected=norm_expected,
                method="deterministic",
            )

        elif score < self.AMBIGUOUS_THRESHOLD:
            return NameMatchResult(
                is_match=False,
                score=score,
                explanation=f"Baja coincidencia ({score:.0%})",
                normalized_provided=norm_provided,
                normalized_expected=norm_expected,
                method="deterministic",
            )

        else:
            # Ambiguous zone (65-85%) - LLM fallback
            logger.info(
                f"Ambiguous score {score:.2f}, using LLM fallback "
                f"(provided='{provided_name}', expected='{expected_name}')"
            )
            try:
                llm_matcher = self._get_llm_matcher()
                llm_result = await llm_matcher.compare(provided_name, expected_name)

                return NameMatchResult(
                    is_match=llm_result.is_match,
                    score=llm_result.score,
                    explanation=llm_result.explanation,
                    normalized_provided=norm_provided,
                    normalized_expected=norm_expected,
                    method="llm",
                )
            except Exception as e:
                logger.error(f"LLM fallback failed: {e}")
                # Fall back to deterministic result with adjusted threshold
                return NameMatchResult(
                    is_match=score >= 0.75,
                    score=score,
                    explanation=f"LLM no disponible, usando score ({score:.0%})",
                    normalized_provided=norm_provided,
                    normalized_expected=norm_expected,
                    method="fallback",
                )

    async def find_best_match(
        self,
        provided_name: str,
        candidates: list[dict[str, Any]],
        name_field: str = "nombre",
    ) -> tuple[dict[str, Any] | None, float]:
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

            # Early exit if very high confidence
            if result.score >= 0.95:
                break

        if best_score >= self.FINAL_MATCH_THRESHOLD:
            logger.info(f"Best name match found: score={best_score:.2f}")
            return best_match, best_score

        logger.info(f"No match above threshold: best_score={best_score:.2f}")
        return None, 0.0

    # =========================================================================
    # Deterministic Matching (Internal)
    # =========================================================================

    def _normalize_name(self, name: str) -> str:
        """
        Normalize name for comparison.

        - Uppercase
        - Remove accents (NFD normalization)
        - Collapse whitespace
        - Strip

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

        # Collapse whitespace
        name = " ".join(name.split())

        return name.strip()

    def _expand_abbreviations(self, name: str) -> str:
        """
        Expand known Spanish name abbreviations.

        Args:
            name: Normalized name

        Returns:
            Name with abbreviations expanded
        """
        tokens = name.split()
        expanded = []

        i = 0
        while i < len(tokens):
            token = tokens[i]

            # Try two-token abbreviations first (e.g., "J CARLOS")
            if i + 1 < len(tokens):
                two_token = f"{token} {tokens[i + 1]}"
                if two_token in self.ABBREVIATIONS:
                    expanded.append(self.ABBREVIATIONS[two_token])
                    i += 2
                    continue

            # Try single token
            if token in self.ABBREVIATIONS:
                expanded.append(self.ABBREVIATIONS[token])
            else:
                expanded.append(token)
            i += 1

        return " ".join(expanded)

    def _deterministic_score(self, norm_provided: str, norm_expected: str) -> float:
        """
        Calculate deterministic match score using rapidfuzz.

        Uses multiple strategies and returns the best score:
        1. token_sort_ratio: Handles word order variations
        2. token_set_ratio: Handles partial names
        3. partial_ratio: Handles substring matches

        Args:
            norm_provided: Normalized provided name
            norm_expected: Normalized expected name

        Returns:
            Score between 0.0 and 1.0
        """
        # Expand abbreviations for both names
        exp_provided = self._expand_abbreviations(norm_provided)
        exp_expected = self._expand_abbreviations(norm_expected)

        # Calculate multiple scores using rapidfuzz
        # token_sort_ratio: Handles "JUAN PEREZ" = "PEREZ JUAN"
        score_sort = fuzz.token_sort_ratio(exp_provided, exp_expected)

        # token_set_ratio: Handles "JUAN" vs "JUAN CARLOS" (partial names)
        score_set = fuzz.token_set_ratio(exp_provided, exp_expected)

        # partial_ratio: Handles substring matches for longer names
        score_partial = fuzz.partial_ratio(exp_provided, exp_expected)

        # Return best score (most favorable to user)
        max_score = max(score_sort, score_set, score_partial)

        # Convert 0-100 to 0.0-1.0
        return max_score / 100.0


__all__ = ["HybridNameMatcher", "NameMatchResult"]
