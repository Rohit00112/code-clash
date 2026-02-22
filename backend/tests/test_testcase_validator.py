from app.services.testcase_validator import testcase_validator


def test_normalizes_legacy_sample_flag():
    payload = {
        "title": "Example",
        "function_name": "solve",
        "test_cases": [
            {"id": 1, "input": [1], "output": 2, "sample": True},
            {"id": 2, "input": [2], "output": 3, "is_sample": False},
        ],
    }
    normalized, warnings = testcase_validator.validate_and_normalize(payload)
    assert normalized["test_cases"][0]["is_sample"] is True
    assert "sample" not in normalized["test_cases"][0]
    assert normalized["test_cases"][1]["is_sample"] is False
    assert isinstance(warnings, list)


def test_assigns_ids_when_missing():
    payload = {
        "function_name": "solve",
        "test_cases": [
            {"input": [1], "output": 1},
            {"input": [2], "output": 4},
        ],
    }
    normalized, _ = testcase_validator.validate_and_normalize(payload)
    assert normalized["test_cases"][0]["id"] == 1
    assert normalized["test_cases"][1]["id"] == 2
