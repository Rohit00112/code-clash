"""Code execution engine - sandboxed code execution with resource limits"""

import subprocess
import tempfile
import os
import json
import time
import platform
import threading
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Limit concurrent code executions to prevent resource exhaustion
_execution_semaphore = threading.Semaphore(max(1, settings.EXECUTION_MAX_PROCESSES))


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

    def _java_vm_flags(self) -> List[str]:
        """
        JVM flags tuned for constrained sandboxes.

        Without these, default JVM code cache reservation can exceed the
        per-process memory limit and fail before compilation/execution starts.
        """
        limit_mb = max(64, int(self.memory_limit))
        heap_mb = max(32, min(128, limit_mb // 2))
        code_cache_mb = max(16, min(64, limit_mb // 4))
        initial_heap_mb = max(8, min(32, heap_mb // 4))
        return [
            f"-Xms{initial_heap_mb}m",
            f"-Xmx{heap_mb}m",
            f"-XX:ReservedCodeCacheSize={code_cache_mb}m",
            "-XX:+UseSerialGC",
        ]

    def _javac_vm_flags(self) -> List[str]:
        return [f"-J{flag}" for flag in self._java_vm_flags()]

    @staticmethod
    def _classify_error(stderr: str) -> str:
        text = (stderr or "").lower()
        if "time limit exceeded" in text or "timed out" in text:
            return "time_limit_exceeded"
        if "compile" in text:
            return "compile_error"
        if "error" in text or "traceback" in text or "exception" in text:
            return "runtime_error"
        return "runtime_error"

    @staticmethod
    def _sanitize_env() -> Dict[str, str]:
        """
        Return a constrained environment for child processes.
        """
        allowed_keys = {
            "PATH",
            "HOME",
            "LANG",
            "LC_ALL",
            "TMPDIR",
            "SystemRoot",
            "WINDIR",
        }
        sanitized = {}
        for key in allowed_keys:
            value = os.environ.get(key)
            if value:
                sanitized[key] = value
        return sanitized

    def _resource_preexec(self, language: Optional[str] = None):
        """
        Apply per-process resource limits on Unix.
        """
        if os.name == "nt":
            return None
        try:
            import resource
        except Exception:
            return None

        mem_bytes = max(16, self.memory_limit) * 1024 * 1024

        def _set_limits():
            # CPU time seconds soft/hard.
            cpu_soft = max(1, int(self.timeout))
            cpu_hard = cpu_soft + 1
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_soft, cpu_hard))

            # Address space.
            # JVM-based tools (java/javac) can require larger virtual address space
            # even when heap/code cache are constrained, so we do not hard-cap RLIMIT_AS
            # for Java processes.
            if language != "java":
                resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))

            # Prevent fork bombs.
            try:
                resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
            except Exception:
                pass

            # File size and open file handles.
            try:
                resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024))
                resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
            except Exception:
                pass

        return _set_limits

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
                    timeout_ms=test_case.get("timeout_ms"),
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
                    "error": str(e),
                    "error_type": "runtime_error"
                })

        passed_count = sum(1 for r in results if r.get("passed", False))
        primary_failure = next((r for r in results if not r.get("passed")), None)

        return {
            "passed": passed_count,
            "total": len(test_cases),
            "test_results": results,
            "total_execution_time": round(total_time, 3),
            "error_type": (primary_failure or {}).get("error_type"),
            "error_message": (primary_failure or {}).get("error"),
        }

    def _execute_single_test(
        self,
        code: str,
        language: str,
        test_input: Any,
        expected_output: Any,
        test_case_id: int,
        timeout_ms: Optional[int],
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
                executable, compile_error = self._compile_if_needed(source_file, language, temp_dir)

                if not executable:
                    return {
                        "test_case_id": test_case_id,
                        "passed": False,
                        "execution_time": 0,
                        "user_output": "",
                        "error": compile_error or "Compilation failed",
                        "error_type": "compile_error",
                    }

                # Format stdin from test input so input() calls work
                stdin_data = self._format_stdin(test_input)

                # Execute
                start_time = time.time()
                run_result = self._run_code(
                    executable,
                    language,
                    temp_dir,
                    user_id,
                    stdin_data,
                    timeout_ms=timeout_ms,
                )
                execution_time = time.time() - start_time
                output = run_result.get("stdout", "").strip()

                if run_result.get("exit_code", 0) != 0:
                    stderr = run_result.get("stderr", "").strip()
                    error_type = self._classify_error(stderr)
                    return {
                        "test_case_id": test_case_id,
                        "passed": False,
                        "execution_time": round(execution_time, 3),
                        "user_output": output,
                        "stderr": stderr,
                        "error": stderr or "Runtime error",
                        "error_type": error_type,
                    }

                # Compare output
                passed = self._compare_output(output, expected_output)

                return {
                    "test_case_id": test_case_id,
                    "passed": passed,
                    "execution_time": round(execution_time, 3),
                    "output": output if passed else None,
                    "user_output": output,
                    "stderr": run_result.get("stderr", "").strip(),
                    "expected": expected_output if not passed else None,
                    "error": None if passed else f"Expected {expected_output}, got {output}",
                    "error_type": None if passed else "wrong_answer",
                }

            except subprocess.TimeoutExpired:
                return {
                    "test_case_id": test_case_id,
                    "passed": False,
                    "execution_time": self.timeout,
                    "user_output": "",
                    "error": "Time Limit Exceeded",
                    "error_type": "time_limit_exceeded",
                }

            except Exception as e:
                logger.error(f"Execution error: {e}")
                err_msg = str(e)
                return {
                    "test_case_id": test_case_id,
                    "passed": False,
                    "execution_time": 0,
                    "user_output": "",
                    "error": err_msg,
                    "error_type": "runtime_error",
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
        """
        Create Java test harness.

        Supports both:
        - input-style solutions that define `main`
        - function-style solutions without `main`
        """
        has_main = re.search(r"\bstatic\s+void\s+main\s*\(", code) is not None

        if isinstance(test_input, list):
            arg_literals = [self._python_to_java_literal(item) for item in test_input]
        else:
            arg_literals = [self._python_to_java_literal(test_input)]
        args_expr = ", ".join(arg_literals)

        if has_main:
            run_logic = "Solution.main(args);"
        else:
            run_logic = (
                f"            Object[] __callArgs = new Object[]{{{args_expr}}};\n"
                f"            Object __result = __invokeSolution(\"{function_name}\", __callArgs);\n"
                "            System.out.println(__toJson(__result));"
            )

        return f"""
{code}

class __Runner {{
    private static Class<?> __boxedType(Class<?> t) {{
        if (!t.isPrimitive()) return t;
        if (t == int.class) return Integer.class;
        if (t == long.class) return Long.class;
        if (t == double.class) return Double.class;
        if (t == float.class) return Float.class;
        if (t == short.class) return Short.class;
        if (t == byte.class) return Byte.class;
        if (t == char.class) return Character.class;
        if (t == boolean.class) return Boolean.class;
        return t;
    }}

    private static boolean __isCompatible(Class<?> paramType, Object arg) {{
        if (arg == null) return !paramType.isPrimitive();
        Class<?> boxed = __boxedType(paramType);
        Class<?> argType = arg.getClass();
        if (boxed.isAssignableFrom(argType)) return true;
        if (Number.class.isAssignableFrom(boxed) && arg instanceof Number) return true;
        if (boxed == Character.class && arg instanceof String s && s.length() == 1) return true;
        return false;
    }}

    private static String __snakeToCamel(String name) {{
        if (name == null || name.isEmpty() || !name.contains("_")) return name;
        StringBuilder sb = new StringBuilder();
        boolean upper = false;
        for (int i = 0; i < name.length(); i++) {{
            char c = name.charAt(i);
            if (c == '_') {{
                upper = true;
                continue;
            }}
            if (upper) {{
                sb.append(Character.toUpperCase(c));
                upper = false;
            }} else {{
                sb.append(c);
            }}
        }}
        return sb.toString();
    }}

    private static java.util.List<String> __candidateMethodNames(String requested) {{
        java.util.LinkedHashSet<String> names = new java.util.LinkedHashSet<>();
        if (requested != null && !requested.isEmpty()) {{
            names.add(requested);
            names.add(__snakeToCamel(requested));
        }}
        return new java.util.ArrayList<>(names);
    }}

    private static java.lang.reflect.Method __findMethod(Class<?> cls, String name, Object[] args) {{
        for (java.lang.reflect.Method m : cls.getDeclaredMethods()) {{
            if (!m.getName().equals(name)) continue;
            Class<?>[] paramTypes = m.getParameterTypes();
            if (paramTypes.length != args.length) continue;
            boolean ok = true;
            for (int i = 0; i < paramTypes.length; i++) {{
                if (!__isCompatible(paramTypes[i], args[i])) {{
                    ok = false;
                    break;
                }}
            }}
            if (ok) return m;
        }}
        return null;
    }}

    private static Object __invokeSolution(String requestedName, Object[] args) throws Exception {{
        Class<?> cls = Solution.class;
        java.lang.reflect.Method target = null;
        for (String name : __candidateMethodNames(requestedName)) {{
            target = __findMethod(cls, name, args);
            if (target != null) break;
        }}
        if (target == null) {{
            throw new NoSuchMethodException(
                "No matching method found for '" + requestedName + "' (also tried snake/camel variants)"
            );
        }}
        target.setAccessible(true);
        Object receiver = java.lang.reflect.Modifier.isStatic(target.getModifiers()) ? null : new Solution();
        return target.invoke(receiver, args);
    }}

    private static String __escape(String s) {{
        if (s == null) return "null";
        return s
            .replace("\\\\", "\\\\\\\\")
            .replace("\\"", "\\\\\\"")
            .replace("\\n", "\\\\n")
            .replace("\\r", "\\\\r")
            .replace("\\t", "\\\\t");
    }}

    private static String __toJson(Object obj) {{
        if (obj == null) return "null";
        if (obj instanceof String || obj instanceof Character) {{
            return "\\"" + __escape(String.valueOf(obj)) + "\\"";
        }}
        if (obj instanceof Number || obj instanceof Boolean) {{
            return String.valueOf(obj);
        }}
        if (obj instanceof java.util.Map<?, ?> map) {{
            StringBuilder sb = new StringBuilder();
            sb.append("{{");
            boolean first = true;
            for (java.util.Map.Entry<?, ?> e : map.entrySet()) {{
                if (!first) sb.append(",");
                sb.append(__toJson(String.valueOf(e.getKey())));
                sb.append(":");
                sb.append(__toJson(e.getValue()));
                first = false;
            }}
            sb.append("}}");
            return sb.toString();
        }}
        if (obj instanceof Iterable<?> it) {{
            StringBuilder sb = new StringBuilder();
            sb.append("[");
            boolean first = true;
            for (Object item : it) {{
                if (!first) sb.append(",");
                sb.append(__toJson(item));
                first = false;
            }}
            sb.append("]");
            return sb.toString();
        }}
        if (obj.getClass().isArray()) {{
            StringBuilder sb = new StringBuilder();
            sb.append("[");
            int len = java.lang.reflect.Array.getLength(obj);
            for (int i = 0; i < len; i++) {{
                if (i > 0) sb.append(",");
                sb.append(__toJson(java.lang.reflect.Array.get(obj, i)));
            }}
            sb.append("]");
            return sb.toString();
        }}
        return "\\"" + __escape(String.valueOf(obj)) + "\\"";
    }}

    public static void main(String[] args) {{
        try {{
            {run_logic}
        }} catch (Throwable e) {{
            System.err.println("ERROR: " + e.getMessage());
            e.printStackTrace(System.err);
            System.exit(1);
        }}
    }}
}}
"""

    def _python_to_java_literal(self, value: Any) -> str:
        """Convert Python values to Java literals for harness invocation."""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            if isinstance(value, float):
                if value != value:
                    return "Double.NaN"
                if value == float("inf"):
                    return "Double.POSITIVE_INFINITY"
                if value == float("-inf"):
                    return "Double.NEGATIVE_INFINITY"
                return repr(value)
            return str(value)
        if isinstance(value, str):
            escaped = (
                value.replace("\\", "\\\\")
                .replace('"', '\\"')
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t")
            )
            return f'"{escaped}"'
        if isinstance(value, list):
            if not value:
                return "new java.util.ArrayList<>()"
            inner = ", ".join(self._python_to_java_literal(item) for item in value)
            return f"new java.util.ArrayList<>(java.util.Arrays.asList({inner}))"
        if isinstance(value, dict):
            entries = []
            for k, v in value.items():
                entries.append(
                    f"put({self._python_to_java_literal(k)}, {self._python_to_java_literal(v)});"
                )
            body = " ".join(entries)
            return (
                "new java.util.HashMap<Object, Object>() {{ "
                f"{body} "
                "}}"
            )
        return self._python_to_java_literal(str(value))

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

    def _compile_if_needed(self, source_file: str, language: str, temp_dir: str) -> Tuple[Optional[str], Optional[str]]:
        """Compile code if necessary"""

        if language in ["python", "javascript"]:
            return source_file, None  # Interpreted languages

        output_file = os.path.join(temp_dir, "solution.exe" if platform.system() == "Windows" else "solution")

        compile_commands = {
            "java": ["javac", *self._javac_vm_flags(), source_file],
            "c": ["gcc", source_file, "-o", output_file, "-lm"],
            "cpp": ["g++", source_file, "-o", output_file, "-std=c++17"],
            "csharp": ["csc", f"/out:{output_file}", source_file]
        }

        if language not in compile_commands:
            return None, "Unsupported language"

        try:
            _execution_semaphore.acquire()
            try:
                result = subprocess.run(
                    compile_commands[language],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=temp_dir,
                    env=self._sanitize_env(),
                    preexec_fn=self._resource_preexec(language),
                )
            finally:
                _execution_semaphore.release()

            if result.returncode != 0:
                logger.error(f"Compilation error: {result.stderr}")
                return None, (result.stderr or result.stdout or "Compilation failed").strip()

            return (output_file if language != "java" else source_file), None

        except Exception as e:
            logger.error(f"Compilation exception: {e}")
            return None, str(e)

    def _run_code(self, executable: str, language: str, temp_dir: str,
                  user_id: Optional[int] = None, stdin_data: str = "",
                  timeout_ms: Optional[int] = None) -> Dict[str, Any]:
        """Run compiled/interpreted code with optional stdin"""
        env = self._sanitize_env()
        if language == "python" and user_id is not None:
            user_env = self.temp_dir / f"user_{user_id}"
            if user_env.exists():
                env["PYTHONPATH"] = str(user_env) + os.pathsep + env.get("PYTHONPATH", "")

        if language == "python":
            cmd = ["python", executable]
        elif language == "java":
            cmd = ["java", *self._java_vm_flags(), "-cp", temp_dir, "__Runner"]
        elif language == "javascript":
            cmd = ["node", executable]
        else:
            cmd = [executable]

        timeout_seconds = self.timeout
        if timeout_ms is not None:
            try:
                timeout_seconds = max(0.1, int(timeout_ms) / 1000.0)
            except Exception:
                timeout_seconds = self.timeout

        _execution_semaphore.acquire()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=temp_dir,
                env=env,
                input=stdin_data if stdin_data else None,
                preexec_fn=self._resource_preexec(language),
            )
        finally:
            _execution_semaphore.release()

        return {
            "stdout": (result.stdout or "").strip(),
            "stderr": (result.stderr or "").strip(),
            "exit_code": result.returncode,
        }

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
                elif language == "java":
                    full_code = self._create_java_harness(code, function_name, test_input)
                elif language == "javascript":
                    full_code = self._create_javascript_raw_harness(code, function_name, test_input)
                else:
                    # For compiled languages, use the normal harness
                    full_code = code

                with open(source_file, 'w', encoding='utf-8') as f:
                    f.write(full_code)

                executable, compile_error = self._compile_if_needed(source_file, language, temp_dir)
                if not executable:
                    return {
                        "stdout": "",
                        "stderr": compile_error or "Compilation failed",
                        "exit_code": 1,
                        "execution_time_ms": 0,
                        "error_type": "compile_error",
                        "error_message": compile_error or "Compilation failed",
                    }

                # Pipe test input as stdin so input() calls work
                stdin_data = self._format_stdin(test_input)
                start_time = time.time()
                result = self._run_code(executable, language, temp_dir, user_id, stdin_data)
                elapsed_ms = int((time.time() - start_time) * 1000)
                stderr = result.get("stderr", "")
                error_type = self._classify_error(stderr) if result.get("exit_code", 0) != 0 else None
                return {
                    "stdout": result.get("stdout", ""),
                    "stderr": stderr,
                    "exit_code": result.get("exit_code", 0),
                    "execution_time_ms": elapsed_ms,
                    "error_type": error_type,
                    "error_message": stderr or None,
                }

            except subprocess.TimeoutExpired:
                return {
                    "stdout": "",
                    "stderr": "Time Limit Exceeded",
                    "exit_code": 124,
                    "execution_time_ms": int(self.timeout * 1000),
                    "error_type": "time_limit_exceeded",
                    "error_message": "Time Limit Exceeded",
                }
            except Exception as e:
                return {
                    "stdout": "",
                    "stderr": str(e),
                    "exit_code": 1,
                    "execution_time_ms": 0,
                    "error_type": "runtime_error",
                    "error_message": str(e),
                }

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
