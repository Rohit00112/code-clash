"""Test case schema validation and normalization."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.core.exceptions import ValidationError


def _bool_value(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return bool(value)


class TestcaseValidator:
    """Strict validator for challenge testcase JSON payloads."""

    @staticmethod
    def _normalize_test_case(tc: Dict[str, Any], index: int) -> Dict[str, Any]:
        errors: List[str] = []
        normalized = dict(tc)

        if "input" not in normalized:
            errors.append(f"test_cases[{index}].input is required")
        if "output" not in normalized:
            errors.append(f"test_cases[{index}].output is required")

        # Canonical sample flag field.
        raw_sample = normalized.get("is_sample", normalized.get("sample"))
        normalized["is_sample"] = _bool_value(raw_sample, default=index < 2)
        normalized.pop("sample", None)

        # Optional metadata fields with validation.
        if "name" in normalized and normalized["name"] is not None:
            if not isinstance(normalized["name"], str) or not normalized["name"].strip():
                errors.append(f"test_cases[{index}].name must be a non-empty string")
            else:
                normalized["name"] = normalized["name"].strip()

        if "weight" in normalized and normalized["weight"] is not None:
            try:
                normalized["weight"] = float(normalized["weight"])
            except (TypeError, ValueError):
                errors.append(f"test_cases[{index}].weight must be numeric")
            else:
                if normalized["weight"] <= 0:
                    errors.append(f"test_cases[{index}].weight must be > 0")

        if "timeout_ms" in normalized and normalized["timeout_ms"] is not None:
            try:
                normalized["timeout_ms"] = int(normalized["timeout_ms"])
            except (TypeError, ValueError):
                errors.append(f"test_cases[{index}].timeout_ms must be an integer")
            else:
                if normalized["timeout_ms"] <= 0:
                    errors.append(f"test_cases[{index}].timeout_ms must be > 0")

        if errors:
            raise ValidationError("Invalid test case", details={"errors": errors})

        return normalized

    @classmethod
    def validate_and_normalize(cls, payload: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        """
        Validate and normalize testcase payload.

        Returns:
            Tuple[normalized_payload, warnings]
        """
        if not isinstance(payload, dict):
            raise ValidationError("Test case payload must be a JSON object")

        function_name = payload.get("function_name")
        if not isinstance(function_name, str) or not function_name.strip():
            raise ValidationError("Test case JSON must have non-empty 'function_name'")

        test_cases = payload.get("test_cases")
        if not isinstance(test_cases, list) or not test_cases:
            raise ValidationError("Test case JSON must have non-empty 'test_cases' array")

        normalized_cases: List[Dict[str, Any]] = []
        ids_seen = set()
        warnings: List[str] = []

        for idx, tc in enumerate(test_cases):
            if not isinstance(tc, dict):
                raise ValidationError(
                    "Invalid test case",
                    details={"errors": [f"test_cases[{idx}] must be an object"]},
                )
            normalized_tc = cls._normalize_test_case(tc, idx)

            case_id = normalized_tc.get("id")
            if case_id is None:
                case_id = idx + 1
            try:
                case_id = int(case_id)
            except (TypeError, ValueError):
                raise ValidationError(
                    "Invalid test case",
                    details={"errors": [f"test_cases[{idx}].id must be an integer"]},
                )
            if case_id <= 0:
                raise ValidationError(
                    "Invalid test case",
                    details={"errors": [f"test_cases[{idx}].id must be > 0"]},
                )
            if case_id in ids_seen:
                raise ValidationError(
                    "Invalid test case",
                    details={"errors": [f"Duplicate test case id: {case_id}"]},
                )
            ids_seen.add(case_id)
            normalized_tc["id"] = case_id
            normalized_cases.append(normalized_tc)

        sample_count = sum(1 for tc in normalized_cases if tc.get("is_sample"))
        hidden_count = len(normalized_cases) - sample_count

        if sample_count == 0:
            warnings.append("No sample test cases defined. Participants will have limited run feedback.")
        if hidden_count < 2:
            warnings.append("Too few hidden test cases. Consider adding more for robust grading.")

        normalized = dict(payload)
        normalized["function_name"] = function_name.strip()
        normalized["test_cases"] = normalized_cases

        # Keep title optional, normalize if present.
        if "title" in normalized and isinstance(normalized["title"], str):
            normalized["title"] = normalized["title"].strip()

        return normalized, warnings


testcase_validator = TestcaseValidator()
