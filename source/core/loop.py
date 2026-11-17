"""The Intercept & Compute loop — the client's beating center.

Extracted from ai-client.py unchanged in behavior: ask the model; if
the reply is a TOOL: token, intercept it, execute it against the ring
services (or, for shell, locally — as it has always been), feed the
result back as a TOOL_RESULT message, and loop — up to max_loops
times — until the model answers in plain text.

The loop is GUI-free. The client injects three callables:

    chat(history) -> str        one Ollama round-trip, stripped text
    emit(text, sender)          surface a bubble ("ai" / "system")
    execute(tool_string) -> str defaults to execute_tool_payload here
"""
import subprocess

from core.models import human_error
from core.protocol import SERVICE_PORTS, is_tool_call, mcp_call, parse_tool_token


def execute_tool_payload(tool_string, call=None):
    """Execute one TOOL: token and format the result for the model.

    Dispatch and result formatting are exactly the client's historical
    behavior, including which actions each service is asked to run.
    `call` is the wire caller (core.protocol.mcp_call by default).
    """
    if call is None:
        call = mcp_call
    try:
        subsystem, action, params = parse_tool_token(tool_string)

        if subsystem == "shell" and action == "exec":
            cmd = params.get("cmd")
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            return f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"

        elif subsystem == "files":
            resp = call(SERVICE_PORTS["files"], params | {"action": action})
            if resp.get("status") == "ok":
                if action == "read":
                    return f"File content ({resp.get('size',0)} bytes):\n{resp.get('content','')}"
                elif action == "write":
                    return f"Wrote {resp.get('written',0)} bytes to {resp.get('path','')}"
                elif action == "search":
                    matches = "\n".join(resp.get("matches", []))
                    return f"Matches:\n{matches}" if matches else "No matches found"
            return f"Files error: {resp.get('message','Unknown')}"

        elif subsystem == "web":
            resp = call(SERVICE_PORTS["web"], params | {"action": action})
            if resp.get("status") == "ok":
                c = resp.get("content", "")
                return f"Web content ({len(c)} chars):\n{c[:2000]}"
            return f"Web error: {resp.get('message','Unknown')}"

        elif subsystem == "vision":
            resp = call(SERVICE_PORTS["vision"], params | {"action": action})
            if resp.get("status") == "ok":
                if action in ("list", "list_cameras"):
                    cams = "\n".join(resp.get("cameras", []))
                    return f"Cameras ({resp.get('count',0)}):\n{cams}"
                elif action in ("capture", "grab"):
                    return f"Frame captured: {resp.get('path','')} ({resp.get('size',0)} bytes)"
            return f"Vision error: {resp.get('message','Unknown')}"

        elif subsystem == "memory":
            resp = call(SERVICE_PORTS["memory"], params | {"action": action})
            if resp.get("status") == "ok":
                if action == "get" or action == "recall":
                    return f"Memory: {resp.get('value','(empty)')}"
                elif action == "set" or action == "store":
                    return "Memory stored"
                elif action in ("list", "list_keys"):
                    entries = "\n".join(f"{e['key']} ({e['ts']})" for e in resp.get("entries", []))
                    return f"Memory keys:\n{entries}" if entries else "No stored keys"
            return f"Memory error: {resp.get('message','Unknown')}"

        elif subsystem == "coding":
            resp = call(SERVICE_PORTS["coding"], params | {"action": action})
            if resp.get("status") == "ok":
                out = resp.get("stdout", "")
                err = resp.get("stderr", "")
                result = ""
                if out: result += f"Output:\n{out}\n"
                if err: result += f"Errors:\n{err}\n"
                if action == "eval" and "result" in resp:
                    result += f"Result: {resp['result']}"
                return result or "(no output)"
            return f"Coding error: {resp.get('message','')}"

        elif subsystem == "sound":
            resp = call(SERVICE_PORTS["sound"], params | {"action": action})
            if resp.get("status") == "ok":
                parts = []
                if "heard" in resp and resp["heard"]:
                    parts.append(f"Heard: {resp['heard']}")
                if resp.get("alarm"): parts.append("⚠️ ALARM DETECTED")
                if resp.get("wake_word"): parts.append("👋 Wake word heard")
                if "cooldown_remaining_s" in resp:
                    parts.append(f"Cooldown: {resp['cooldown_remaining_s']}s")
                return "\n".join(parts) if parts else "Sound service OK"
            return f"Sound error: {resp.get('message','Unknown')}"

        elif subsystem == "voice":
            resp = call(SERVICE_PORTS["voice"], params | {"action": action})
            if resp.get("status") == "ok":
                return f"Voice: {resp.get('engine','')} - \"{resp.get('text','')[:60]}\""
            return f"Voice error: {resp.get('message','Unknown')}"

    except Exception as e:
        return f"Tool error: {str(e)}"
    return "Unknown tool command."


def run_tool_loop(history, chat, emit, execute=None, max_loops=5):
    """Run the Intercept & Compute cycle against a live history list.

    history is mutated in place (tool exchanges and the final answer
    are appended), exactly as the client's inline loop mutated it.
    """
    if execute is None:
        execute = execute_tool_payload
    loop_count = 0
    while loop_count < max_loops:
        try:
            ai_output = chat(history)
            if is_tool_call(ai_output):
                emit(f"⚙️ Tool:\n{ai_output}", "system")
                tool_result = execute(ai_output)

                history.append({"role": "assistant", "content": ai_output})
                history.append({"role": "user", "content": f"TOOL_RESULT: {tool_result}"})
                loop_count += 1
                continue
            else:
                emit(ai_output, "ai")
                history.append({"role": "assistant", "content": ai_output})
                break
        except Exception as e:
            emit(human_error(e), "ai")
            break
