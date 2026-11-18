"""Ring service scaffold — the lifecycle every MCP service runs.

Geometrically nested systems repeat the same lifecycle at every layer:

    register  ->  bind a port under a name and a ring
    serve     ->  accept one JSON request per connection, dispatch it
                  to the service's handler dict, reply, close
    report    ->  answer {"action": "health"} with the service's
                  transductive health: name, ring, port, uptime

The wire contract is unchanged from the original hand-rolled loops:
recv up to 65536 bytes, one reply, connection closed, and errors never
kill the loop. Per-service quirks are preserved through parameters —
the unknown-action message format differs between services, and the
coding service reports malformed JSON as "Invalid JSON" where the
others surface the parser's message.
"""
import ast
import json
import re
import socket
import time

from core.protocol import error, ok

# ------------------------------------------------------------------
# Service labels — how a script plug joins the build.
#
# A script becomes part of the app by exactly two steps:
#   1. SOURCE LABELED — the script carries a label block:
#          Label-Name: memory
#          Label-Origin: ai-core-workspace build
#          Label-Version: 1
#          Label-Hash: <optional content hash / provenance note>
#          Label-Does: key/value memory over the wire protocol
#      (in the module docstring or in leading comments — the
#      parser below accepts both).
#   2. ROUTED — a route entry: the service's serve() call (name,
#      ring, port, actions) agrees with core.protocol.SERVICE_PORTS.
# A script that is unlabeled or unrouted is a census finding
# (core.selfmaint), never silently enabled; a labeled + routed
# script is picked up on the next wake/dwell beat. Expansion rides
# these existing organs — there is no separate expansion engine.
# ------------------------------------------------------------------

LABEL_KEYS = ("name", "origin", "version", "hash", "does")
_LABEL_RE = re.compile(
    r"Label-(Name|Origin|Version|Hash|Does)\s*:\s*(.+?)\s*$",
    re.MULTILINE)


def parse_label(text):
    """Extract a service label from source text.

    Returns a dict of the Label-* fields found (lowercased keys),
    or None when the script carries no label at all. A label is
    complete when name, origin, version and does are present
    (hash is a provenance extra).
    """
    found = {}
    for key, value in _LABEL_RE.findall(text or ""):
        found[key.lower()] = value.strip()
    return found or None


def label_complete(label):
    """True when a parsed label has every required field."""
    if not label:
        return False
    return all(label.get(k) for k in ("name", "origin",
                                      "version", "does"))


def label_block(name, origin, version, does, hash_note=None):
    """Render a label block (comment form) for a script header."""
    lines = ["# --- AI Core service label ---",
             f"# Label-Name: {name}",
             f"# Label-Origin: {origin}",
             f"# Label-Version: {version}"]
    if hash_note:
        lines.append(f"# Label-Hash: {hash_note}")
    lines.append(f"# Label-Does: {does}")
    lines.append("# --- end label ---")
    return "\n".join(lines)


def serve_route(source_text):
    """Parse a service file's serve() call into a route dict.

    Returns {"name", "ring", "port", "actions"} or None. The port
    may be a literal or a module-level constant (PORT = 9108).
    This is the route a labeled script declares; the census
    compares it against core.protocol.SERVICE_PORTS.
    """
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return None
    consts = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) \
                and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    consts[target.id] = node.value.value
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Name) and func.id == "serve"):
            continue
        if len(node.args) < 4:
            continue

        def _val(n):
            if isinstance(n, ast.Constant):
                return n.value
            if isinstance(n, ast.Name):
                return consts.get(n.id)
            return None

        name, ring, port = (_val(node.args[0]), _val(node.args[1]),
                            _val(node.args[2]))
        if name is None or port is None:
            continue
        actions = []
        if isinstance(node.args[3], ast.Dict):
            for key in node.args[3].keys:
                if isinstance(key, ast.Constant):
                    actions.append(key.value)
        return {"name": name, "ring": ring, "port": port,
                "actions": sorted(actions)}
    return None


class RingService:
    """A named service, in a named ring, on its historical port."""

    def __init__(self, name, ring, port, handlers, host="127.0.0.1",
                 unknown_fmt="Unknown action: {action}", json_error=None):
        self.name = name
        self.ring = ring
        self.port = port
        self.host = host
        self.unknown_fmt = unknown_fmt
        self.json_error = json_error
        self.started = time.time()
        self.handlers = dict(handlers)
        # Transductive health is a citizen of every ring — unless the
        # service already owns the "health" action (the web service's
        # predates this convention and keeps its meaning).
        if "health" not in self.handlers:
            self.handlers["health"] = self._health

    def _health(self, req):
        return ok(service=self.name, ring=self.ring, port=self.port,
                  uptime_s=round(time.time() - self.started, 1))

    def handle(self, data):
        """Dispatch one raw request (str or bytes) to a response dict."""
        try:
            req = json.loads(data)
        except Exception as e:
            if self.json_error is not None:
                return error(self.json_error)
            return error(str(e))
        try:
            action = req.get("action", "ping")
        except Exception as e:
            return error(str(e))
        handler = self.handlers.get(action)
        if handler is None:
            return error(self.unknown_fmt.format(action=action))
        try:
            return handler(req)
        except Exception as e:
            return error(str(e))

    def serve(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.host, self.port))
        s.listen(5)
        while True:
            try:
                conn, _addr = s.accept()
                data = conn.recv(65536)
                if data:
                    conn.sendall(json.dumps(self.handle(data.decode())).encode())
                conn.close()
            except Exception:
                pass


def serve(name, ring, port, handlers, **kwargs):
    """Register and serve one ring service (blocks forever)."""
    RingService(name, ring, port, handlers, **kwargs).serve()
