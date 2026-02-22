from app.services.code_executor import code_executor


def test_compare_output_json_equivalence():
    assert code_executor._compare_output('["a", "b"]', ["a", "b"]) is True


def test_run_once_returns_structured_fields():
    code = """
def solve(x):
    print(x * 2)
"""
    result = code_executor.run_once(
        code=code,
        language="python",
        function_name="solve",
        test_input=[5],
        user_id=None,
    )
    assert "stdout" in result
    assert "stderr" in result
    assert "exit_code" in result
    assert "execution_time_ms" in result
