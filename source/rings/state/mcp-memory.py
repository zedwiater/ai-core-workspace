# --- AI Core service label ---
# Label-Name: memory
# Label-Origin: ai-core-workspace build (Zak/Muse)
# Label-Version: 1
# Label-Does: SQLite-backed key/value memory over the wire protocol
# --- end label ---
#!/usr/bin/env python3
"""George's MCP Memory Service — persistent key-value store

Ring: state (inner ring — holds state, close to the core).
Runs the shared ring lifecycle: register -> serve -> report health.
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from core.ring_service import serve

PORT = 9108


def _db_path():
    """Installed layout first (/opt/ai-core, when it exists and is
    writable); a user-space fallback otherwise. A state node must
    never die at import because a root-owned tree isn't there yet —
    found live 2026-11-17: the node crash-looped on PermissionError
    whenever /opt/ai-core was absent or not yet chowned."""
    env = os.environ.get("AI_CORE_MEMORY_DB")
    if env:
        return env
    base = "/opt/ai-core"
    if os.path.isdir(base) and os.access(base, os.W_OK):
        return os.path.join(base, "george_memory.db")
    fallback = os.path.expanduser("~/.local/share/ai-core")
    os.makedirs(fallback, exist_ok=True)
    return os.path.join(fallback, "george_memory.db")


DB = _db_path()


def init():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB); c.execute("CREATE TABLE IF NOT EXISTS mem (key TEXT PRIMARY KEY, val TEXT, ts TEXT)")
    c.commit(); c.close()


def ping(req):
    return {"status": "pong"}


def get(req):
    c = sqlite3.connect(DB)
    r = c.execute("SELECT val FROM mem WHERE key=?", (req["key"],)).fetchone()
    return {"status": "ok", "value": r[0] if r else None}


def set_key(req):
    c = sqlite3.connect(DB)
    c.execute("REPLACE INTO mem VALUES (?,?,datetime('now'))", (req["key"], req["value"])); c.commit()
    return {"status": "ok"}


def list_keys(req):
    c = sqlite3.connect(DB)
    r = c.execute("SELECT key, ts FROM mem ORDER BY ts DESC LIMIT 50").fetchall()
    return {"status": "ok", "entries": [{"key": k, "ts": t} for k, t in r]}


def delete(req):
    c = sqlite3.connect(DB)
    c.execute("DELETE FROM mem WHERE key=?", (req["key"],)); c.commit()
    return {"status": "ok"}


init()

if __name__ == "__main__":
    serve("memory", "state", PORT,
          {"ping": ping, "get": get, "set": set_key, "list": list_keys, "delete": delete},
          unknown_fmt="Unknown: {action}")
