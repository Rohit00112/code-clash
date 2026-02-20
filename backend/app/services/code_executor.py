"""Code execution engine - sandboxed code execution with resource limits"""

import subprocess
import tempfile
import os
import json
import time
import platform
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.config import settings
from app.core.exceptions import CodeExecutionError
import logging

logger = logging.getLogger(__name__)

# Limit concurrent code executions to prevent resource exhaustion
_execution_semaphore = threading.Semaphore(10)


class CodeExecutor:
    """Secure code execution engine"""

    LANGUAGE_EXTENSIONS = {
        "python": ".py",
        "java": ".java",
        "c": ".c",
        "cpp": ".cpp",
        "javascript": ".js",
        "csharp": ".cs"
    }

    def __init__(self):
        self.timeout = settings.CODE_EXECUTION_TIMEOUT
        self.memory_limit = settings.CODE_EXECUTION_MEMORY_LIMIT
        self.temp_dir = Path(settings.get_temp_dir())
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _format_stdin(test_input: Any) -> str:
        """Convert test case input to stdin string for interactive input() support.

        Examples:
            [10] -> "10\\n"
            ["abc", "def"] -> "abc\\ndef\\n"
            [[1,2,3], [4,5,6]] -> "1 2 3\\n4 5 6\\n"
            [["cbaebabacd", "abc"]] -> "cbaebabacd\\nabc\\n"
        """
        if test_input is None:
            return ""

        lines = []
        if isinstance(test_input, list):
            for item in test_input:
                if isinstance(item, list):
                    lines.append(" ".join(str(x) for x in item))
                else:
                    lines.append(str(item))
        else:
            lines.append(str(test_input))

        return "\n".join(lines) + "\n"

    def execute_code(
        self,
        code: str,
        language: str,
        test_cases: List[Dict[str, Any]],
        function_name: str,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute code against test cases

        Args:
            code: Source code
            language: Programming language
            test_cases: List of test cases
            function_name: Function name to test

        Returns:
            Execution results
        """
        results = []
        total_time = 0.0

        for test_case in test_cases:
            try:
                result = self._execute_single_test(
                    code=code,
                    language=language,
                    test_input=test_case.get("input"),
                    expected_output=test_case.get("output"),
                    test_case_id=test_case.get("id"),
                    function_name=function_name,
                    user_id=user_id
                )
                results.append(result)
                total_time += result.get("execution_time", 0)

            except Exception as e:
                logger.error(f"Error executing test case {test_case.get('id')}: {e}")
                results.append({
                    "test_case_id": test_case.get("id"),
                    "passed": False,
                    "execution_time": 0,
                    "error": str(e)
                })

        passed_count = sum(1 for r in results if r.get("passed", False))

        return {
            "passed": passed_count,
            "total": len(test_cases),
            "test_results": results,
            "total_execution_time": round(total_time, 3)
        }

    def _execute_single_test(
        self,
        code: str,
        language: str,
        test_input: Any,
        expected_output: Any,
        test_case_id: int,
        function_name: str,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Execute single test case"""

        with tempfile.TemporaryDirectory(dir=self.temp_dir) as temp_dir:
            try:
                # Create source file
                source_file = self._create_source_file(
                    temp_dir, code, language, function_name, test_input
                )

                # Compile if needed
                executable = self._compile_if_needed(source_file, language, temp_dir)

                if not executable:
                    return {
                        "test_case_id": test_case_id,
                        "passed": False,
                        "execution_time": 0,
                        "user_output": "",
                        "error": "Compilation failed"
                    }

                # Format stdin from test input so input() calls work
                stdin_data = self._format_stdin(test_input)

                # Execute
                start_time = time.time()
                output = self._run_code(executable, language, temp_dir, user_id, stdin_data)
                execution_time = time.time() - start_time

                # Compare output
                passed = self._compare_output(output, expected_output)

                return {
                    "test_case_id": test_case_id,
                    "passed": passed,
                    "execution_time": round(execution_time, 3),
                    "output": output if passed else None,
                    "user_output": output,
                    "expected": expected_output if not passed else None,
                    "error": None if passed else f"Expected {expected_output}, got {output}"
                }

            except subprocess.TimeoutExpired:
                return {
                    "test_case_id": test_case_id,
                    "passed": False,
                    "execution_time": self.timeout,
                    "user_output": "",
                    "error": "Time Limit Exceeded"
                }

            except Exception as e:
                logger.error(f"Execution error: {e}")
                err_msg = str(e)
                user_out = err_msg.replace("Runtime error: ", "").strip() if "Runtime error:" in err_msg else ""
                return {
                    "test_case_id": test_case_id,
                    "passed": False,
                    "execution_time": 0,
                    "user_output": user_out,
                    "error": err_msg
                }

    def _create_source_file(
        self,
        temp_dir: str,
        code: str,
        language: str,
        function_name: str,
        test_input: Any
    ) -> str:
        """Create source file with test harness"""

        extension = self.LANGUAGE_EXTENSIONS.get(language, ".txt")
        source_file = os.path.join(temp_dir, f"Solution{extension}")

        # Add test harness based on language
        if language == "python":
            full_code = self._create_python_harness(code, function_name, test_input)
        elif language == "java":
            full_code = self._create_java_harness(code, function_name, test_input)
        elif language in ["c", "cpp"]:
            full_code = self._create_c_cpp_harness(code, function_name, test_input, language)
        elif language == "javascript":
            full_code = self._create_javascript_harness(code, function_name, test_input)
        elif language == "csharp":
            full_code = self._create_csharp_harness(code, function_name, test_input)
        else:
            full_code = code

        with open(source_file, 'w', encoding='utf-8') as f:
            f.write(full_code)

        return source_file

    def _create_python_harness(self, code: str, function_name: str, test_input: Any) -> str:
        """Create Python test harness.

        If the user defines the expected function, call it with test_input args
        and print the JSON result (function-style).
        If the user does NOT define it (input()-style code), the code already ran
        at module level using stdin — just exit cleanly.
        """
        return f"""
import json
import sys

{code}

if __name__ == "__main__":
    try:
        if "{function_name}" in dir() or callable(globals().get("{function_name}")):
            test_input = {json.dumps(test_input)}
            if isinstance(test_input, list):
                result = {function_name}(*test_input)
            else:
                result = {function_name}(test_input)
            print(json.dumps(result))
    except Exception as e:
        print(f"ERROR: {{e}}", file=sys.stderr)
        sys.exit(1)
"""

    def _create_java_harness(self, code: str, function_name: str, test_input: Any) -> str:
        """Create Java test harness"""
        return code

    def _create_c_cpp_harness(self, code: str, function_name: str, test_input: Any, language: str) -> str:
        """Create C/C++ test harness"""
        return code

    def _create_javascript_harness(self, code: str, function_name: str, test_input: Any) -> str:
        """Create JavaScript test harness.

        If the user defines the expected function, call it.
        If not (stdin-style code), the code already ran at top level.
        """
        return f"""
{code}

if (typeof {function_name} === 'function') {{
    const testInput = {json.dumps(test_input)};
    try {{
        let result;
        if (Array.isArray(testInput)) {{
            result = {function_name}(...testInput);
        }} else {{
            result = {function_name}(testInput);
        }}
        console.log(JSON.stringify(result));
    }} catch (e) {{
        console.error('ERROR:', e.message);
        process.exit(1);
    }}
}}
"""

    def _create_csharp_harness(self, code: str, function_name: str, test_input: Any) -> str:
        """Create C# test harness"""
        return code

    def _compile_if_needed(self, source_file: str, language: str, temp_dir: str) -> Optional[str]:
        """Compile code if necessary"""

        if language in ["python", "javascript"]:
            return source_file  # Interpreted languages

        output_file = os.path.join(temp_dir, "solution.exe" if platform.system() == "Windows" else "solution")

        compile_commands = {
            "java": ["javac", source_file],
            "c": ["gcc", source_file, "-o", output_file, "-lm"],
            "cpp": ["g++", source_file, "-o", output_file, "-std=c++17"],
            "csharp": ["csc", f"/out:{output_file}", source_file]
        }

        if language not in compile_commands:
            return None

        try:
            _execution_semaphore.acquire()
            try:
                result = subprocess.run(
                    compile_commands[language],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=temp_dir
                )
            finally:
                _execution_semaphore.release()

            if result.returncode != 0:
                logger.error(f"Compilation error: {result.stderr}")
                return None

            return output_file if language != "java" else source_file

        except Exception as e:
            logger.error(f"Compilation exception: {e}")
            return None

    def _run_code(self, executable: str, language: str, temp_dir: str,
                  user_id: Optional[int] = None, stdin_data: str = "") -> str:
        """Run compiled/interpreted code with optional stdin"""
        env = os.environ.copy()
        if language == "python" and user_id is not None:
            user_env = self.temp_dir / f"user_{user_id}"
            if user_env.exists():
                env["PYTHONPATH"] = str(user_env) + os.pathsep + env.get("PYTHONPATH", "")

        if language == "python":
            cmd = ["python", executable]
        elif language == "java":
            cmd = ["java", "-cp", temp_dir, "Solution"]
        elif language == "javascript":
            cmd = ["node", executable]
        else:
            cmd = [executable]

        _execution_semaphore.acquire()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=temp_dir,
                env=env,
                input=stdin_data if stdin_data else None
            )
        finally:
            _execution_semaphore.release()

        if result.returncode != 0:
            raise CodeExecutionError(f"Runtime error: {result.stderr}")

        return result.stdout.strip()

    def _compare_output(self, output: str, expected: Any) -> bool:
        """Compare output with expected result"""

        output_stripped = str(output).strip()
        expected_stripped = str(expected).strip()

        # Direct string comparison
        if output_stripped == expected_stripped:
            return True

        # Try JSON parsing both sides
        try:
            output_parsed = json.loads(output_stripped)
            if output_parsed == expected:
                return True
            # Also try parsing expected as JSON for symmetric comparison
            try:
                expected_parsed = json.loads(expected_stripped)
                if output_parsed == expected_parsed:
                    return True
            except (json.JSONDecodeError, TypeError):
                pass
        except (json.JSONDecodeError, TypeError):
            pass

        # Try numeric comparison
        try:
            return float(output_stripped) == float(expected_stripped)
        except (ValueError, TypeError):
            pass

        return False


    def run_once(
        self,
        code: str,
        language: str,
        function_name: str,
        test_input: Any,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Run code once and return raw output. No test case comparison.
        Used for participant test-run so they can experiment freely.
        """
        with tempfile.TemporaryDirectory(dir=self.temp_dir) as temp_dir:
            try:
                # Create source with a raw harness (no JSON result printing)
                extension = self.LANGUAGE_EXTENSIONS.get(language, ".txt")
                source_file = os.path.join(temp_dir, f"Solution{extension}")

                if language == "python":
                    full_code = self._create_python_raw_harness(code, function_name, test_input)
                elif language == "javascript":
                    full_code = self._create_javascript_raw_harness(code, function_name, test_input)
                else:
                    # For compiled languages, use the normal harness
                    full_code = code

                with open(source_file, 'w', encoding='utf-8') as f:
                    f.write(full_code)

                executable = self._compile_if_needed(source_file, language, temp_dir)
                if not executable:
                    return {"output": "", "error": "Compilation failed"}

                # Pipe test input as stdin so input() calls work
                stdin_data = self._format_stdin(test_input)
                output = self._run_code(executable, language, temp_dir, user_id, stdin_data)
                return {"output": output, "error": None}

            except subprocess.TimeoutExpired:
                return {"output": "", "error": "Time Limit Exceeded"}
            except CodeExecutionError as e:
                err = str(e).replace("Runtime error: ", "")
                return {"output": "", "error": err}
            except Exception as e:
                return {"output": "", "error": str(e)}

    def _create_python_raw_harness(self, code: str, function_name: str, test_input: Any) -> str:
        """Python harness for test-run: just runs code, shows prints only.

        If the user defines the expected function, call it with test_input.
        If not (input()-style code), the code already ran at module level
        reading from stdin — nothing more to do.
        """
        return f"""
import json
import sys

{code}

if __name__ == "__main__":
    try:
        if "{function_name}" in dir() or callable(globals().get("{function_name}")):
            test_input = {json.dumps(test_input)}
            if isinstance(test_input, list):
                {function_name}(*test_input)
            else:
                {function_name}(test_input)
    except Exception as e:
        print(f"Error: {{e}}", file=sys.stderr)
        sys.exit(1)
"""

    def _create_javascript_raw_harness(self, code: str, function_name: str, test_input: Any) -> str:
        """JavaScript harness for test-run: just runs code, shows console.log only.

        If the user defines the expected function, call it.
        If not (stdin-style code), the code already ran at top level.
        """
        return f"""
{code}

if (typeof {function_name} === 'function') {{
    const testInput = {json.dumps(test_input)};
    try {{
        if (Array.isArray(testInput)) {{
            {function_name}(...testInput);
        }} else {{
            {function_name}(testInput);
        }}
    }} catch (e) {{
        console.error('Error:', e.message);
        process.exit(1);
    }}
}}
"""


# Singleton instance
code_executor = CodeExecutor()
