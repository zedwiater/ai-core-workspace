"""Shared protocol code for AI Core Workspace.

Two surfaces, one contract:

1. The model surface — tool tokens the model emits and the client
   intercepts, of the form:

       TOOL:<service>:<action>:<json-params>

2. The wire surface — what actually travels on the TCP sockets between
   the client and the ring services: one JSON object per connection,

       {"action": "<action>", ...params}  ->  {"status": ..., ...}

Every service also answers {"action": "ping"} with {"status": "pong"}
(the liveness check), and every service answers {"action": "health"}
with its transductive health report (see core/ring_service.py). The
one exception is the web service, whose "health" action predates this
convention and probes internet reachability instead.
"""
import json
import socket

# Service name -> TCP port. Mirrors source/config.json ("mcp_ports").
SERVICE_PORTS = {
    "files": 9101,
    "web": 9102,
    "vision": 9103,
    "shell": 9104,
    "sound": 9105,
    "voice": 9106,
    "coding": 9107,
    "memory": 9108,
    "dwell": 9109,
}

TOOL_PREFIX = "TOOL:"


# --- Model surface: TOOL: tokens -------------------------------------

def is_tool_call(text):
    """True if a model response is a tool token to intercept."""
    return text.startswith(TOOL_PREFIX)


def parse_tool_token(tool_string):
    """Split 'TOOL:<service>:<action>:<json>' into (service, action, params).

    Raises (IndexError, ValueError) on malformed tokens, exactly as the
    inline parsing in the client always did.
    """
    parts = tool_string.split(":", 3)
    subsystem = parts[1]
    action = parts[2]
    params = json.loads(parts[3])
    return subsystem, action, params


def build_tool_token(subsystem, action, params=None):
    """Assemble a TOOL: token (inverse of parse_tool_token)."""
    return f"{TOOL_PREFIX}{subsystem}:{action}:{json.dumps(params or {})}"


# --- Wire surface: JSON over TCP --------------------------------------

def mcp_call(port, payload, host="127.0.0.1", timeout=5):
    """Send one JSON payload to a service socket and return its reply.

    On any failure returns {"status": "error", "message": str(e)} —
    the behavior the client has always relied on.
    """
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.sendall(json.dumps(payload).encode())
        resp = json.loads(s.recv(65536).decode())
        s.close()
        return resp
    except Exception as e:
        return {"status": "error", "message": str(e)}


def call_service(service, action, params=None, timeout=None):
    """Call a service by name: payload is params merged with the action,
    the action key winning — the merge order the client has always used.
    Slow organs (a mic capture chain, an RTSP grab) need a longer
    timeout than the default — pass it explicitly.
    """
    payload = dict(params or {})
    payload["action"] = action
    if timeout is None:
        return mcp_call(SERVICE_PORTS[service], payload)
    return mcp_call(SERVICE_PORTS[service], payload,
                    timeout=timeout)


# --- Response constructors (service side) ------------------------------

def ok(**fields):
    """A successful service response: {"status": "ok", ...}."""
    return {"status": "ok", **fields}


def pong(**fields):
    """The liveness response: {"status": "pong", ...}."""
    return {"status": "pong", **fields}


def error(message):
    """A failed service response: {"status": "error", "message": ...}."""
    return {"status": "error", "message": message}
