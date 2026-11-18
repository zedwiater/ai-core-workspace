"""The privilege agreement — three levels, the user's choice,
changeable any time (Zak, 2026-11-18: 'three agrees of install
— to begin setup chatbot/search assist no permissions granted,
or All. From shell to files deletion. We can include
disclaimer.').

The levels, in order:
- observer: begin setup. Chatbot + search assist; NO
  permissions granted — no shell, no file operations, no
  service calls. The floor observes and reports.
- connected: the local organs work — models seat, quick
  actions run, services answer for reading and speaking.
  Shell and file changes stay out.
- all: full attachment. Shell commands and file operations,
  deletion included, run locally under the disclaimer below.

Default is observer: gain autonomy, gauge comfort (the first
job on open). Offerings — advice, suggestions, links — default
ON at every level; the user can turn them off later.
"""
import json
import os

LEVELS = [
    {"id": "observer",
     "name": "Observer — no permissions granted",
     "blurb": "Begin setup as a chatbot + search assistant. "
              "Nothing on this machine is touched: no shell, no "
              "files, no service calls. The app observes and "
              "reports."},
    {"id": "connected",
     "name": "Connected — local organs",
     "blurb": "Models seat, quick actions run, services answer "
              "for reading and speaking. Shell commands and "
              "file changes stay out."},
    {"id": "all",
     "name": "All — full attachment",
     "blurb": "Everything Connected allows, plus shell "
              "commands and file operations — including "
              "deletion — run locally, under the disclaimer."},
]

DISCLAIMER = (
    "Disclaimer for All: the app can run shell commands and "
    "change or delete files on this machine, at your direction. "
    "That power is the point of the tier and the risk of it. "
    "Keep it on only while you want it — the switch is yours, "
    "in the open, on the Conduit page, and dropping back takes "
    "effect immediately.")

_ORDER = [lv["id"] for lv in LEVELS]

# capability -> minimum level
_MINIMUM = {
    "chat": "observer",
    "web": "observer",
    "seat": "connected",
    "quick": "connected",
    "services": "connected",
    "shell": "all",
    "files_write": "all",
}

_WRITE_ACTIONS = ("write", "delete", "remove", "move", "rename",
                  "mkdir", "create", "append", "trash")


def level_index(level):
    return _ORDER.index(level) if level in _ORDER else 0


def allows(level, capability):
    """True when `level` grants `capability`. Unknown levels
    read as observer; unknown capabilities are refused."""
    if capability not in _MINIMUM:
        return False
    return level_index(level) >= level_index(_MINIMUM[capability])


def gate_for_tool(service, action=""):
    """The capability a tool call needs: shell is its own tier;
    file writes/deletes are the top tier; file reads and every
    other service ride at Connected."""
    if service == "shell":
        return "shell"
    if service == "files":
        a = (action or "").lower()
        if any(w in a for w in _WRITE_ACTIONS):
            return "files_write"
        return "services"
    return "services"


def refusal(level, capability):
    need = _MINIMUM.get(capability, "all")
    need_name = next((lv["name"] for lv in LEVELS
                      if lv["id"] == need), need)
    return (f"🔒 That needs the {need_name} agreement — yours "
            f"is {level}. Nothing was run. Raise the agreement "
            f"on the Conduit page if you want this.")


def load(path):
    """The saved level from a conduit.json-shaped file;
    observer when absent or unreadable."""
    try:
        with open(path) as f:
            data = json.load(f)
        level = data.get("agreement", "observer")
        return level if level in _ORDER else "observer"
    except Exception:
        return "observer"


def save(path, level):
    """Persist the level into the conduit.json-shaped file,
    preserving its other keys. Returns the level saved."""
    if level not in _ORDER:
        level = "observer"
    data = {}
    try:
        with open(path) as f:
            data = json.load(f)
    except Exception:
        pass
    data["agreement"] = level
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=1)
    return level
