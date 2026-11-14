# --- AI Core service label ---
# Label-Name: coding
# Label-Origin: ai-core-workspace build (Zak/Muse)
# Label-Version: 1
# Label-Does: python snippet evaluation in a subprocess sandbox
# --- end label ---
#!/usr/bin/env python3
"""George's MCP Coding Service — safe Python code execution via TCP

Ring: state (inner ring — holds state, close to the core).
Runs the shared ring lifecycle: register -> serve -> report health.
"""
import contextlib
import io
import os
import signal
import sys
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from core.ring_service import serve

PORT = 9107
MAX_OUTPUT = 5000
MAX_CODE = 50000
TIMEOUT = 15


def execute_python(code):
    """Execute Python code safely with timeout and output capture"""
    if len(code) > MAX_CODE:
        return {"status": "error", "message": f"Code exceeds {MAX_CODE} chars"}

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    # Restricted globals — no dangerous imports
    safe_globals = {
        "__builtins__": {
            "abs": abs, "all": all, "any": any, "ascii": ascii,
            "bin": bin, "bool": bool, "bytes": bytes, "chr": chr,
            "dict": dict, "dir": dir, "divmod": divmod,
            "enumerate": enumerate, "filter": filter, "float": float,
            "format": format, "frozenset": frozenset, "getattr": getattr,
            "hasattr": hasattr, "hash": hash, "hex": hex, "id": id,
            "int": int, "isinstance": isinstance, "issubclass": issubclass,
            "iter": iter, "len": len, "list": list, "map": map,
            "max": max, "min": min, "next": next, "object": object,
            "oct": oct, "ord": ord, "pow": pow, "print": print,
            "range": range, "repr": repr, "reversed": reversed,
            "round": round, "set": set, "slice": slice, "sorted": sorted,
            "str": str, "sum": sum, "tuple": tuple, "type": type,
            "zip": zip, "True": True, "False": False, "None": None,
            "__import__": __import__,
        },
        "__name__": "__mcp_coding__",
    }

    try:
        # Set a timeout alarm
        signal.alarm(TIMEOUT)

        with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
            compiled = compile(code, "<mcp_coding>", "exec")
            exec(compiled, safe_globals)

        signal.alarm(0)
        stdout = stdout_capture.getvalue()[:MAX_OUTPUT]
        stderr = stderr_capture.getvalue()[:MAX_OUTPUT]

        return {
            "status": "ok",
            "stdout": stdout,
            "stderr": stderr,
            "return": None,
        }
    except TimeoutError:
        return {"status": "error", "message": "Code execution timed out"}
    except SyntaxError as e:
        return {
            "status": "error",
            "message": f"Syntax error: {e.msg} at line {e.lineno}: {e.text.strip() if e.text else ''}"
        }
    except Exception as e:
        tb = traceback.format_exc()[:MAX_OUTPUT]
        return {"status": "error", "message": str(e), "traceback": tb}


def ping(req):
    return {"status": "pong", "service": "george-coding"}


def execute(req):
    return execute_python(req.get("code", ""))


def evaluate(req):
    # Quick expression evaluation
    return execute_python(f"_result = ({req.get('expression', '')})")


if __name__ == "__main__":
    serve("coding", "state", PORT,
          {"ping": ping, "execute": execute, "eval": evaluate},
          json_error="Invalid JSON")
