"""
JSON extraction utility for parsing LLM responses that may contain
additional formatting, thinking blocks, or markdown code blocks.
"""

import json
import logging
import re
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)


def extract_json_from_text(
    text: str,
    default: Optional[Union[Dict[str, Any], list]] = None,
    required_keys: Optional[list[str]] = None,
) -> Union[Dict[str, Any], list, None]:
    """
    Extract JSON from text that may contain additional formatting.

    Handles various formats including:
    - <think> blocks
    - Markdown code blocks (```json, ```)
    - Plain JSON
    - Partial JSON extraction as fallback

    Args:
        text: The text containing JSON data
        default: Default value to return if extraction fails
        required_keys: Optional list of keys that must be present in the JSON

    Returns:
        Parsed JSON object (dict or list) or default value if extraction fails
    """
    if not text:
        logger.warning("Empty text provided for JSON extraction")
        return default

    try:
        # Step 1: Remove thinking tags if present
        clean_text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

        # Step 2: Try to find JSON in various formats
        json_patterns = [
            # Markdown code blocks with json language
            r"```json\s*(\{.*?\}|\[.*?\])\s*```",
            # Generic markdown code blocks
            r"```\s*(\{.*?\}|\[.*?\])\s*```",
            # JSON object or array without code blocks
            r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})",
            r"(\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\])",
        ]

        for pattern in json_patterns:
            matches = re.findall(pattern, clean_text, re.DOTALL)
            for match in matches:
                potential_json = match.strip() if isinstance(match, str) else match[0].strip()
                try:
                    parsed = json.loads(potential_json)

                    # Validate required keys if specified
                    if required_keys and isinstance(parsed, dict):
                        if all(key in parsed for key in required_keys):
                            logger.debug(f"Successfully extracted JSON with required keys: {required_keys}")
                            return parsed
                        else:
                            logger.debug(f"JSON missing required keys: {required_keys}")
                            continue

                    logger.debug("Successfully extracted JSON from text")
                    return parsed

                except json.JSONDecodeError as e:
                    logger.debug(f"Failed to parse potential JSON: {e}")
                    continue

        # Step 3: Try direct parsing (in case the entire text is valid JSON)
        try:
            parsed = json.loads(text.strip())

            # Validate required keys if specified
            if required_keys and isinstance(parsed, dict):
                if not all(key in parsed for key in required_keys):
                    logger.warning(f"Direct parsed JSON missing required keys: {required_keys}")
                    return default

            logger.debug("Text was already valid JSON")
            return parsed

        except json.JSONDecodeError:
            pass

        # Step 4: Fallback - try to extract partial JSON by looking for key patterns
        if required_keys:
            logger.debug("Attempting partial JSON extraction based on required keys")
            extracted_data = {}

            for key in required_keys:
                # Try to find key-value pairs in various formats
                patterns = [
                    rf'"{key}"\s*:\s*"([^"]*)"',  # String value
                    rf'"{key}"\s*:\s*(\d+\.?\d*)',  # Number value
                    rf'"{key}"\s*:\s*(true|false)',  # Boolean value
                    rf'"{key}"\s*:\s*(null)',  # Null value
                    rf'"{key}"\s*:\s*(\[[^\]]*\])',  # Array value
                ]

                for pattern in patterns:
                    match = re.search(pattern, clean_text, re.IGNORECASE)
                    if match:
                        value = match.group(1)

                        # Try to parse the value appropriately
                        if value in ["true", "false"]:
                            extracted_data[key] = value == "true"
                        elif value == "null":
                            extracted_data[key] = None
                        elif value.startswith("["):
                            try:
                                extracted_data[key] = json.loads(value)
                            except:
                                extracted_data[key] = []
                        else:
                            # Try to convert to number if possible
                            try:
                                if "." in value:
                                    extracted_data[key] = float(value)
                                else:
                                    extracted_data[key] = int(value)
                            except:
                                extracted_data[key] = value
                        break

            if extracted_data and all(key in extracted_data for key in required_keys):
                logger.info(f"Successfully extracted partial JSON with keys: {list(extracted_data.keys())}")
                return extracted_data

        logger.warning("Could not extract valid JSON from text")
        return default

    except Exception as e:
        logger.error(f"Error extracting JSON from text: {str(e)}")
        return default


def extract_json_safely(
    text: str,
    expected_type: type = dict,
    default: Optional[Union[Dict[str, Any], list]] = None,
) -> Union[Dict[str, Any], list, None]:
    """
    Safely extract JSON ensuring it matches the expected type.

    Args:
        text: The text containing JSON data
        expected_type: Expected type of the JSON (dict or list)
        default: Default value to return if extraction fails

    Returns:
        Parsed JSON of the expected type or default value
    """
    result = extract_json_from_text(text, default)

    if result is not None and not isinstance(result, expected_type):
        logger.warning(f"Extracted JSON is not of expected type {expected_type.__name__}")
        return default

    return result
