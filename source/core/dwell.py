# --- AI Core module label ---
# Label-Name: dwell
# Label-Origin: ai-core-workspace build (Zak/Muse)
# Label-Version: 1
# Label-Does: the dwell loop's shared state — config, timeline,
#   review queue, attention and emergency arithmetic
# --- end label ---
"""Dwell: the app's own slow attention (Zak, 2026-11-18).

George's roam proved the shape on the house stack; this is
the app-native version, sized to whatever machine it lands
on. A background service patrols the machine's OWN cameras
and microphone on a tier-timed dwell — idle-time work, low
priority — and keeps three honest records:

- a timeline (what was seen/heard, when, how loud)
- a review queue (frames waiting for eyes, attention first)
- a state file (last cycle, queue depth, last attention)

Attention snaps: a sound that rises fast, or a frame that
changes a lot, pulls an immediate extra grab and a priority
place in the queue. Emergencies — a classified alarm from
the sound service, or loud sound sustained across samples —
go out on Telegram (core/notify) with a 10-minute dedupe,
and are labelled for exactly what detected them, never
more.
"""
import json
import os
import time

DWELL_DIR = os.path.expanduser("~/.cache/ai-core/dwell")
FRAMES_DIR = os.path.join(DWELL_DIR, "frames")
TIMELINE = os.path.join(DWELL_DIR, "timeline.jsonl")
QUEUE = os.path.join(DWELL_DIR, "review-queue.jsonl")
STATE = os.path.join(DWELL_DIR, "state.json")
CONDUIT_JSON = os.path.expanduser(
    "~/.config/ai-core/conduit.json")

LOUD_DB = -14.0        # sustained above this = emergency-class
ATTENTION_DB = -22.0   # a rise past this snaps attention
FRAME_DELTA = 0.4      # frame size change that counts as motion
RETENTION_S = 24 * 3600
QUEUE_CAP = 300
DEDUPE_S = 600


def dwell_default_s(ram_gb):
    """The tier sets the pace: small machines dwell slowly."""
    if ram_gb >= 24:
        return 30
    if ram_gb >= 10:
        return 45
    return 60


def load_loop_config(path=None):
    try:
        with open(path or CONDUIT_JSON) as f:
            data = json.load(f)
        cfg = data.get("dwell_loop") or {}
    except Exception:
        cfg = {}
    return {"enabled": bool(cfg.get("enabled", False)),
            "dwell_s": int(cfg.get("dwell_s") or 45)}


def save_loop_config(enabled, dwell_s, path=None):
    path = path or CONDUIT_JSON
    data = {}
    try:
        with open(path) as f:
            data = json.load(f)
    except Exception:
        data = {}
    data["dwell_loop"] = {"enabled": bool(enabled),
                          "dwell_s": int(dwell_s)}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=1)
    return data["dwell_loop"]


def _append(path, entry):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _read_last(path, n):
    try:
        with open(path) as f:
            lines = f.readlines()
    except OSError:
        return []
    out = []
    for line in lines[-n:]:
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def log_timeline(entry):
    entry = {"ts": time.time(), **entry}
    _append(TIMELINE, entry)
    return entry


def read_timeline(n=20):
    return _read_last(TIMELINE, n)


def enqueue(frame_path, cam, reason, level_db=None):
    entry = {"ts": time.time(), "cam": cam, "path": frame_path,
             "reason": reason, "level_db": level_db,
             "status": "pending"}
    _append(QUEUE, entry)
    return entry


def queue_entries(n=50):
    return _read_last(QUEUE, n)


def queue_depth():
    try:
        with open(QUEUE) as f:
            return sum(1 for line in f
                       if '"pending"' in line)
    except OSError:
        return 0


def save_state(state):
    os.makedirs(DWELL_DIR, exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(state, f, indent=1)


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except Exception:
        return {}


def sound_rose(prev_db, cur_db, threshold=ATTENTION_DB,
               rise=6.0):
    """A snap of attention: quiet, then suddenly not."""
    if cur_db is None or cur_db < threshold:
        return False
    if prev_db is None:
        return True
    return (cur_db - prev_db) >= rise or prev_db < threshold


def frame_changed(prev_size, size, delta=FRAME_DELTA):
    if not prev_size or not size:
        return False
    return abs(size - prev_size) / prev_size > delta


def loud_sustained(levels, loud=LOUD_DB):
    """Emergency-class by level alone: the last two samples
    both loud. Labelled as loud sound — never as a named
    alarm — because level alone cannot classify."""
    recent = [lv for lv in levels if lv is not None][-2:]
    return len(recent) == 2 and all(lv > loud for lv in recent)


def prune(now=None):
    """Frames older than the retention window go; the queue
    keeps at most QUEUE_CAP newest entries."""
    now = now or time.time()
    removed = 0
    if os.path.isdir(FRAMES_DIR):
        for root, _dirs, files in os.walk(FRAMES_DIR):
            for name in files:
                p = os.path.join(root, name)
                try:
                    if now - os.path.getmtime(p) > RETENTION_S:
                        os.remove(p)
                        removed += 1
                except OSError:
                    pass
    try:
        with open(QUEUE) as f:
            lines = f.readlines()
        if len(lines) > QUEUE_CAP:
            with open(QUEUE, "w") as f:
                f.writelines(lines[-QUEUE_CAP:])
    except OSError:
        pass
    return removed
