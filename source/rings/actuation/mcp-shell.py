# --- AI Core service label ---
# Label-Name: shell
# Label-Origin: ai-core-workspace build (Zak/Muse)
# Label-Version: 1
# Label-Does: shell command execution for the app's tool loop
# --- end label ---
#!/usr/bin/env python3
"""George's MCP Shell Service — real shell execution via TCP socket

Ring: actuation (middle ring — acts on the machine).
Runs the shared ring lifecycle: register -> serve -> report health.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from core.ring_service import serve

PORT = 9104


def ping(req):
    return {"status": "pong"}


def exec_command(req):
    """Process a shell exec request"""
    try:
        cmd = req.get("cmd", "")
        timeout = min(req.get("timeout", 10), 30)
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return {"status": "ok", "stdout": result.stdout[:5000], "stderr": result.stderr[:1000], "code": result.returncode}
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "Command timed out"}


if __name__ == "__main__":
    serve("shell", "actuation", PORT,
          {"ping": ping, "exec": exec_command})
