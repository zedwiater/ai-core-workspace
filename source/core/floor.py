"""Themes and the base floor — what the app is, and what always runs.

Two ideas live here, nested one inside the other:

1. THEMES. The Joy Calculator's beginning-depth outcome becomes the
   theme the app runs under. Each depth level maps to a named theme
   (THEMES); the theme is the relationship the app proposes on
   opening — the header reads "Relationship: <theme>". The
   shallowest outcome is a first-class theme, not a failure:
   level 1, "Plain Chatbot & Reminders", is the DEFAULT theme —
   what the app runs under when no theme has been set, and what a
   person can pick directly ("start plain") without ever taking
   the calculator.

2. THE BASE FLOOR. Nested inside EVERY theme, including plain:
   reality intelligence alignment monitors — wake and dwell only.
   The back end compares its own live state to the expected map
   (reach home first: what answers {"action": "health"} across the
   eight ring services, against the name/ring/port each should
   report) on exactly two beats:
     wake  — once, when the app opens / a session starts
     dwell — on a periodic background tick (DWELL_INTERVAL_S)
   At no other time. Each check records an alignment snapshot to
   the memory service under floor:<session>:alignment — services
   up/down, mismatches named plainly, timestamp. A service down or
   a mismatch is the monitor doing its job; the app keeps running.

All theme names and behaves-as lines below are DRAFT wording in
Zak's plain register, written for his red pen.
"""
import json
import os
import threading
import time

from core.intake import DEPTH_LEVELS
from core.protocol import SERVICE_PORTS, mcp_call

MEMORY_PORT = SERVICE_PORTS["memory"]

# The base floor's name, exactly as framed: the monitors run on two
# beats and no others, in every theme there is.
FLOOR_DOCTRINE = ("reality intelligence alignment monitors — "
                  "wake and dwell only")

DWELL_INTERVAL_S = 15 * 60  # the dwell beat: 15 minutes, the lab cadence

# The floor note every theme carries — the floor does not get
# quieter in shallower themes.
FLOOR_NOTE = ("Base floor: reality intelligence alignment monitors "
              "run in this theme too — on wake and dwell only. The "
              "back end checks its own live state when the app opens "
              "and on the dwell beat, and at no other time.")

# --- Themes (ALL NAMES + BEHAVES-AS LINES ARE DRAFT WORDING) -----------
# One theme per Joy Calculator depth level, keyed by level. Level 1
# is Zak's shallow pole as a theme in its own right: plain chatbot
# and reminder, chosen on purpose by plenty of people.
_THEME_COPY = {
    1: ("Plain Chatbot & Reminders",
        "The app answers when you ask and keeps your reminders. "
        "Nothing reaches out first and nothing watches along — "
        "just a chatbot and a reminder app, on purpose."),
    2: ("Helper on Call",
        "The app remembers what you ask it to remember and lends a "
        "hand when you come to it. It starts nothing on its own."),
    3: ("Keeper of the Threads",
        "The app keeps track of the threads of your life alongside "
        "you, holding what matters so less of it slips."),
    4: ("Companion in the Loop",
        "The app is in the loop with you: it checks in, notices "
        "changes, and carries the thread of your days."),
    5: ("Hyper Processing Lives",
        "The app runs woven into your life, processing alongside "
        "you as it happens — a presence, not a tool you visit."),
}

THEMES = []
for _entry in DEPTH_LEVELS:
    _name, _behaves = _THEME_COPY[_entry["level"]]
    THEMES.append({
        "level": _entry["level"],
        "name": _name,
        "depth_name": _entry["name"],
        "behaves_as": _behaves,
        "floor_note": FLOOR_NOTE,
    })

THEME_BY_LEVEL = {t["level"]: t for t in THEMES}

# The default theme option: plain. Unset anywhere — fresh install,
# memory service silent, no calculator run — means this theme.
DEFAULT_THEME = THEME_BY_LEVEL[1]

THEME_KEY = "app:theme"


def theme_for_level(level):
    """The theme for a depth level (clamped to the scale)."""
    level = max(THEMES[0]["level"], min(THEMES[-1]["level"], int(level)))
    return THEME_BY_LEVEL[level]


def theme_for_depth(depth):
    """The theme a compute_depth() result begins under."""
    return theme_for_level(depth["level"])


# --- Theme persistence: the memory service holds the standing theme ---

def save_theme(theme, set_by, port=MEMORY_PORT):
    """Record the standing theme under app:theme. Returns success."""
    resp = mcp_call(port, {"action": "set", "key": THEME_KEY,
                           "value": json.dumps({
                               "level": theme["level"],
                               "name": theme["name"],
                               "set_by": set_by,
                               "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                           })}, timeout=2)
    return resp.get("status") == "ok"


def load_theme(port=MEMORY_PORT):
    """Read the standing theme: (theme, set_by).

    Falls back to the plain default theme when nothing is stored or
    the memory service can't be reached — plain is the default theme
    option, so an unset app is a plain app, never a broken one.
    """
    resp = mcp_call(port, {"action": "get", "key": THEME_KEY}, timeout=2)
    raw = resp.get("value")
    if raw:
        try:
            data = json.loads(raw)
            theme = THEME_BY_LEVEL.get(int(data["level"]))
            if theme is not None:
                return theme, data.get("set_by", "stored")
        except (TypeError, ValueError, KeyError):
            pass
    return DEFAULT_THEME, "default"


# --- The base floor: alignment on wake and dwell only -----------------

# The expected map: what each ring service should report about
# itself. Ports come from core.protocol (the wire contract); rings
# mirror the source/rings/ tree.
_RING_OF = {
    "files": "actuation",
    "web": "atmosphere",
    "vision": "atmosphere",
    "shell": "actuation",
    "sound": "atmosphere",
    "voice": "atmosphere",
    "coding": "state",
    "memory": "state",
}
EXPECTED_SERVICES = {
    name: {"ring": _RING_OF[name], "port": port}
    for name, port in SERVICE_PORTS.items()
}


def probe_services(timeout=2):
    """Reach home first: ask every ring service for its live state.

    Returns {name: response-dict} for services that answered
    {"action": "health"} in any form, with unanswering services
    absent. The web service is the known exception: its "health"
    probes internet reachability (and can fail for reasons that are
    not the service being down), so if its health doesn't come back
    ok we fall back to its ping — a pong means web itself is up.
    """
    live = {}
    for name, port in SERVICE_PORTS.items():
        resp = mcp_call(port, {"action": "health"}, timeout=timeout)
        if resp.get("status") == "error" and name == "web":
            resp = mcp_call(port, {"action": "ping"}, timeout=timeout)
            if resp.get("status") == "pong":
                resp = {"status": "ok", "via": "ping"}
        if resp.get("status") != "error":
            live[name] = resp
    return live


def build_snapshot(beat, session, theme, live, beat_count=None):
    """Compare a live map against the expected map -> one snapshot.

    Pure function of the map probe_services() returns; the seven
    ring services report service/ring/port about themselves, and
    those are checked against EXPECTED_SERVICES field by field.
    Web reports no identity in-band (its health predates the ring
    convention), so for web only up/down is checked, and the
    snapshot says so. Down services and mismatches are listed
    plainly — that is the monitor doing its job.
    """
    services = {}
    up, down, mismatches = [], [], []
    for name, expected in EXPECTED_SERVICES.items():
        resp = live.get(name)
        if resp is None:
            down.append(name)
            services[name] = {"up": False,
                              "expected_ring": expected["ring"],
                              "expected_port": expected["port"]}
            continue
        up.append(name)
        detail = {"up": True}
        for field in ("ring", "port", "uptime_s", "reachable"):
            if field in resp:
                detail[field] = resp[field]
        if resp.get("via") == "ping":
            detail["note"] = ("identity by ping only — web's health "
                              "predates the ring convention")
        for field in ("service", "ring", "port"):
            if field not in resp:
                continue
            want = name if field == "service" else expected[field]
            if resp[field] != want:
                mismatches.append(
                    f"{name}: reports {field} {resp[field]!r}, "
                    f"expected {want!r}")
        services[name] = detail
    snapshot = {
        "floor": FLOOR_DOCTRINE,
        "beat": beat,
        "session": session,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "theme": {"level": theme["level"], "name": theme["name"]}
        if theme else None,
        "aligned": not down and not mismatches,
        "up": up,
        "down": down,
        "mismatches": mismatches,
        "services": services,
    }
    if beat_count is not None:
        snapshot["beat_count"] = beat_count
    return snapshot


def record_snapshot(snapshot, port=MEMORY_PORT):
    """Write one alignment snapshot under floor:<session>:alignment.
    Returns success; a silent memory service never breaks the app."""
    resp = mcp_call(port, {
        "action": "set",
        "key": f"floor:{snapshot['session']}:alignment",
        "value": json.dumps(snapshot),
    }, timeout=2)
    return resp.get("status") == "ok"


class FloorMonitor:
    """The base floor, running: wake once, then dwell ticks.

    A lightweight timer thread; checks never block the caller and
    never raise. The monitor holds the client's standing theme
    (assign .theme when the theme changes) and stamps it into each
    snapshot. stop() ends the dwell thread cleanly.
    """

    def __init__(self, session_id=None, interval=DWELL_INTERVAL_S,
                 theme=None, port=MEMORY_PORT, probe_timeout=2,
                 companion=None, daughters_probe=None):
        self.session_id = session_id or (
            f"{int(time.time())}-{threading.get_ident() % 100000}")
        self.interval = interval
        self.theme = theme
        self.port = port
        self.probe_timeout = probe_timeout
        # Optional beat companions, both guarded, both called with
        # the finished snapshot: `companion` is where self-
        # maintenance rides the same beats (never mid-conversation,
        # never a third beat); `daughters_probe` lets a parent's
        # snapshot carry its daughters' brief ages (core.hybrid).
        self.companion = companion
        self.daughters_probe = daughters_probe
        self.last_snapshot = None
        self._beats = 0
        self._stop = threading.Event()
        self._thread = None

    def check(self, beat):
        """One alignment check on the given beat ('wake'/'dwell').

        Probes the live state, builds the snapshot, records it to
        the memory service, and returns it. Never raises.
        """
        try:
            live = probe_services(timeout=self.probe_timeout)
            self._beats += 1
            snapshot = build_snapshot(beat, self.session_id,
                                      self.theme, live,
                                      beat_count=self._beats)
            snapshot["recorded"] = record_snapshot(snapshot,
                                                   port=self.port)
            # Process-count sanity, when the OS offers it cheaply:
            # the night of 2026-11-13 the host's process table
            # filled until nothing could start a thread. A count
            # in every snapshot makes that shape visible in the
            # record. Guarded — a missing /proc just omits it.
            try:
                snapshot["processes"] = sum(
                    1 for p in os.listdir("/proc") if p.isdigit())
            except Exception:
                pass
            if self.daughters_probe is not None:
                try:
                    daughters = self.daughters_probe()
                    if daughters:
                        snapshot["daughters"] = daughters
                except Exception:
                    pass
            self.last_snapshot = snapshot
            if self.companion is not None:
                try:
                    self.companion(snapshot)
                except Exception:
                    pass
            return snapshot
        except Exception:
            return None

    def wake(self):
        """The wake beat: one check, run when the app opens."""
        return self.check("wake")

    def start(self):
        """Start the dwell beat: a check every interval, forever
        until stop(). The wake beat is wake()'s job, not this loop's.
        """
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._dwell_loop,
                                        daemon=True)
        self._thread.start()

    def _dwell_loop(self):
        while not self._stop.wait(self.interval):
            self.check("dwell")

    def stop(self):
        """End the dwell beat cleanly."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
