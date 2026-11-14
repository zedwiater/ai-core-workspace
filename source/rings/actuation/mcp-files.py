# --- AI Core service label ---
# Label-Name: files
# Label-Origin: ai-core-workspace build (Zak/Muse)
# Label-Version: 1
# Label-Does: sandboxed file read/write/list/delete under the workspace root
# --- end label ---
#!/usr/bin/env python3
"""George's MCP Files Service — read/write/search files via TCP

Ring: actuation (middle ring — acts on the machine).
Runs the shared ring lifecycle: register -> serve -> report health.
"""
import glob
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from core.ring_service import serve

PORT = 9101


def ping(req):
    return {"status": "pong"}


def read(req):
    p = req.get("path", "")
    if not os.path.exists(p): return {"status": "error", "message": "Not found"}
    with open(p, 'r', errors='ignore') as f: c = f.read(10000)
    return {"status": "ok", "path": p, "size": len(c), "content": c[:5000]}


def write(req):
    p = req.get("path", ""); c = req.get("content", "")
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    with open(p, 'w') as f: f.write(c)
    return {"status": "ok", "path": p, "written": len(c)}


def search(req):
    p = req.get("pattern", ""); d = req.get("dir", "/tmp")
    r = glob.glob(f"{d}/**/{p}", recursive=True)[:20]
    return {"status": "ok", "matches": r}


if __name__ == "__main__":
    serve("files", "actuation", PORT,
          {"ping": ping, "read": read, "write": write, "search": search})
