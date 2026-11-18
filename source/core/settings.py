"""App options — the doors' settings, held the way the app holds things.

The Options view is buttons, not a config file: grouped choices, each
with its cost in one line. Choices persist through the memory ring
service under app:options — the same pattern the standing theme uses
(core.floor.save_theme) — as one JSON document. When the memory
service can't be reached, the app runs on the defaults below and the
choices still apply to the running session; nothing pretends they
were written down when they weren't (set() reports whether the write
landed).

Groups (see docs/APP_EXPERIENCE_AND_HARNESS.md, "Options everywhere"):

  patience    dwell_minutes (the floor's dwell beat), turn_timeout_s
              (one model round-trip), explainer_dwell_ms (how long a
              hover must dwell before its explainer opens)
  cadence     indicator — how fast the sidebar's live dots poll:
              full / polite / quiet (CADENCE_SECONDS)
  senses      one on/off per ring service: whether the CHAT may use
              the organ. The base floor checks every organ regardless
              — alignment doesn't take orders from this page.
  redundancy  degradation_notices — whether a dwell snapshot that
              finds a newly-down organ also leaves a note in chat.
              Snapshots are written either way.
  cloud       policy (never / draft / allowed) + session_budget —
              how the Models view's non-local entries may answer.
              Enforced by core.models at chat time.
  hybrid      role (parent / daughter / hybrid), this daughter's
              id, the parent endpoint it briefs, and how old a
              brief may be before the parent calls it stale
              (core.hybrid). The pairing secret itself never lives
              here — it sits in the local secrets file (core.setup).

All option copy (labels, cost lines) lives in the client; this module
is the store and the rules. Values are validated against ALLOWED —
an out-of-range write is refused, never clamped into a lie.
"""
import json

from core.protocol import SERVICE_PORTS, mcp_call

MEMORY_PORT = SERVICE_PORTS["memory"]
OPTIONS_KEY = "app:options"

DEFAULTS = {
    "patience": {
        "dwell_minutes": 15,
        "turn_timeout_s": 30,
        "explainer_dwell_ms": 800,
    },
    "cadence": {
        "indicator": "full",
    },
    "senses": {name: True for name in SERVICE_PORTS},
    "redundancy": {
        "degradation_notices": True,
    },
    "cloud": {
        "policy": "draft",
        "session_budget": 10,
    },
    "hybrid": {
        "role": "parent",
        "daughter_id": "daughter-1",
        "parent_host": "127.0.0.1",
        "parent_port": 9108,
        "stale_minutes": 45,
    },
}

ALLOWED = {
    "patience": {
        "dwell_minutes": (5, 15, 30, 60),
        "turn_timeout_s": (15, 30, 60, 120, 300),
        "explainer_dwell_ms": (300, 800, 1500),
    },
    "cadence": {
        "indicator": ("full", "polite", "quiet"),
    },
    "senses": {name: (True, False) for name in SERVICE_PORTS},
    "redundancy": {
        "degradation_notices": (True, False),
    },
    "cloud": {
        "policy": ("never", "draft", "allowed"),
        "session_budget": (0, 10, 25, None),  # None = no cap
    },
    "hybrid": {
        "role": ("parent", "daughter", "hybrid"),
        "stale_minutes": (15, 30, 45, 90),
    },
}

# Free-form keys: validated by shape, not by enumeration — the
# daughter's name and the parent's address are the owner's words.
FREEFORM = {("hybrid", "daughter_id"), ("hybrid", "parent_host"),
            ("hybrid", "parent_port")}

# Cadence scaling: how many seconds between sidebar indicator polls.
CADENCE_SECONDS = {"full": 2.5, "polite": 7.5, "quiet": 15.0}


def _merge(raw):
    """Defaults with a stored document laid over them, validated."""
    merged = {g: dict(vals) for g, vals in DEFAULTS.items()}
    if not raw:
        return merged
    try:
        stored = json.loads(raw)
    except (TypeError, ValueError):
        return merged
    if not isinstance(stored, dict):
        return merged
    for group, values in stored.items():
        if group not in DEFAULTS or not isinstance(values, dict):
            continue
        for key, value in values.items():
            if (group, key) in FREEFORM:
                if key == "parent_port":
                    if isinstance(value, int) and 1 <= value <= 65535:
                        merged[group][key] = value
                elif isinstance(value, str) and value.strip():
                    merged[group][key] = value
            elif value in ALLOWED[group].get(key, ()):
                merged[group][key] = value
    return merged


class Options:
    """The app's standing choices, with memory-service persistence."""

    def __init__(self, values=None, call=None, port=MEMORY_PORT):
        self._values = values if values is not None else _merge(None)
        self._call = call or mcp_call
        self._port = port

    @classmethod
    def load(cls, call=None, port=MEMORY_PORT):
        """Read app:options from the memory service (defaults when
        it's silent — an unset app is a default app, never broken)."""
        call = call or mcp_call
        resp = call(port, {"action": "get", "key": OPTIONS_KEY},
                    timeout=2)
        return cls(_merge(resp.get("value")), call=call, port=port)

    def get(self, group, key):
        return self._values[group][key]

    def set(self, group, key, value):
        """Set one choice. Returns True when the value is valid (it
        applies to this session either way); the write to the memory
        service is best-effort and reported by persisted()."""
        if (group, key) in FREEFORM:
            if key == "parent_port":
                if not isinstance(value, int) \
                        or not (1 <= value <= 65535):
                    return False
            elif not isinstance(value, str) or not value.strip():
                return False
        elif value not in ALLOWED.get(group, {}).get(key, ()):
            return False
        self._values[group][key] = value
        self._persisted = self._write()
        return True

    def _write(self):
        resp = self._call(self._port, {
            "action": "set", "key": OPTIONS_KEY,
            "value": json.dumps(self._values)}, timeout=2)
        return resp.get("status") == "ok"

    def persisted(self):
        """Whether the last set() reached the memory service."""
        return getattr(self, "_persisted", None)

    # -- derived views the client wires for real ---------------------

    def dwell_seconds(self):
        return self.get("patience", "dwell_minutes") * 60

    def indicator_seconds(self):
        return CADENCE_SECONDS[self.get("cadence", "indicator")]

    def sense_live(self, service):
        return bool(self._values["senses"].get(service, True))

    def as_dict(self):
        return {g: dict(v) for g, v in self._values.items()}
