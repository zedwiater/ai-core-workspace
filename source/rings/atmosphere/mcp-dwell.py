# --- AI Core service label ---
# Label-Name: dwell
# Label-Origin: ai-core-workspace build (Zak/Muse)
# Label-Version: 1
# Label-Does: the app's own patrol — tier-timed camera grabs
#   and mic samples, attention snaps, a review queue, and an
#   emergency monitor with Telegram alerts
# --- end label ---
#!/usr/bin/env python3
"""AI Core Dwell Service — the resident observer.

Ring: atmosphere. Runs the shared ring lifecycle. The loop
itself lives here; its arithmetic and records live in
core/dwell so the app pages read the same truth. The loop
is OFF until the user switches it on (Dwell page or the
set action) — an observer the user didn't ask for is a
bug, not a feature.
"""
import os
import shutil
import socket
import sys
import threading
import time

sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..")))
from core import dwell as dwell_mod
from core import notify as notify_mod
from core.protocol import call_service
from core.ring_service import serve

PORT = 9109
HOST = socket.gethostname()

_lock = threading.Lock()
_state = {"levels": [], "prev_sizes": {}, "rotate": 0,
          "last_alert": 0.0, "last_cycle": None,
          "last_attention": None, "cycles": 0}


def _grab(cam, reason, level_db):
    g = call_service("vision", "grab", {"camera": cam},
                     timeout=45)
    if g.get("status") != "ok" or not g.get("path"):
        fails = _state.setdefault("fails", {})
        fails[cam] = fails.get(cam, 0) + 1
        dwell_mod.log_timeline(
            {"kind": "grab-failed", "cam": cam,
             "why": g.get("message", "no frame")})
        return None
    _state.setdefault("fails", {})[cam] = 0
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest_dir = os.path.join(dwell_mod.FRAMES_DIR,
                            cam.replace("/", "_"))
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, stamp + ".jpg")
    try:
        shutil.copyfile(g["path"], dest)
    except OSError:
        dest = g["path"]
    size = os.path.getsize(dest) if os.path.exists(dest) else 0
    prev = _state["prev_sizes"].get(cam)
    _state["prev_sizes"][cam] = size
    changed = dwell_mod.frame_changed(prev, size)
    entry = dwell_mod.enqueue(
        dest, cam,
        "attention" if reason == "attention" or changed
        else reason, level_db)
    dwell_mod.log_timeline(
        {"kind": "frame", "cam": cam, "path": dest,
         "size": size, "changed": changed, "reason": reason,
         "level_db": level_db})
    return entry


def _alert(text):
    now = time.time()
    if now - _state["last_alert"] < dwell_mod.DEDUPE_S:
        return {"sent": False, "why": "deduped (10 min)"}
    _state["last_alert"] = now
    return notify_mod.send(text)


def run_cycle():
    """One patrol. Never raises — a sick cycle is a logged
    cycle, not a dead service."""
    if not _lock.acquire(blocking=False):
        return {"status": "busy"}
    try:
        cfg = dwell_mod.load_loop_config()
        if not cfg["enabled"]:
            return {"status": "off"}
        lvl = call_service("sound", "level", {"duration": 2},
                           timeout=45)
        level_db = lvl.get("level_db") \
            if lvl.get("status") == "ok" else None
        prev_level = _state["levels"][-1] \
            if _state["levels"] else None
        rose = dwell_mod.sound_rose(prev_level, level_db)
        _state["levels"] = (_state["levels"] + [level_db])[-4:]
        dwell_mod.log_timeline({"kind": "listen",
                                "level_db": level_db,
                                "input": lvl.get("input"),
                                "why": lvl.get("message")})

        lst = call_service("vision", "list")
        cams = lst.get("cameras", []) \
            if lst.get("status") == "ok" else []
        # the plain 'webcam' alias and its named twins are
        # one physical eye — patrol named cameras + the
        # alias only when it is the sole local entry
        patrol = [c for c in cams if c != "webcam"] or cams
        # a camera that keeps failing (a metadata node, an
        # unplugged eye) leaves the rotation after 3 strikes
        # instead of failing into the timeline forever
        fails = _state.get("fails", {})
        patrol = [c for c in patrol if fails.get(c, 0) < 3] \
            or patrol
        grabbed = []
        if patrol:
            step = 2 if len(patrol) > 2 else len(patrol)
            start = _state["rotate"] % len(patrol)
            chosen = [patrol[(start + i) % len(patrol)]
                      for i in range(step)]
            _state["rotate"] = (start + step) % len(patrol)
            for cam in chosen:
                e = _grab(cam, "attention" if rose else "patrol",
                          level_db)
                if e:
                    grabbed.append(e["path"])
            if rose and patrol[0] not in chosen:
                _grab(patrol[0], "attention", level_db)

        if rose:
            _state["last_attention"] = time.time()
            dwell_mod.log_timeline(
                {"kind": "attention", "why": "sound rose",
                 "level_db": level_db})

        emergency = dwell_mod.loud_sustained(_state["levels"])
        alert_result = None
        if emergency:
            _state["last_attention"] = time.time()
            dwell_mod.log_timeline(
                {"kind": "emergency",
                 "why": "loud sound sustained",
                 "level_db": level_db})
            alert_result = _alert(
                f"🚨 AI Core on {HOST}: loud sound sustained "
                f"across samples (latest {level_db} dB). "
                f"This is a level alert, not a classified "
                f"alarm — check the room when you can.")
            if patrol:
                _grab(patrol[0], "emergency", level_db)

        _state["last_cycle"] = time.time()
        _state["cycles"] += 1
        dwell_mod.prune()
        dwell_mod.save_state(
            {"last_cycle": _state["last_cycle"],
             "cycles": _state["cycles"],
             "last_level": level_db,
             "last_attention": _state["last_attention"],
             "queue_depth": dwell_mod.queue_depth()})
        return {"status": "ok", "grabbed": grabbed,
                "level_db": level_db, "rose": rose,
                "emergency": emergency,
                "alert": alert_result}
    except Exception as e:
        dwell_mod.log_timeline({"kind": "cycle-error",
                                "why": str(e)})
        return {"status": "error", "message": str(e)}
    finally:
        _lock.release()


def _loop():
    try:
        os.nice(10)  # dwell is idle-time work
    except OSError:
        pass
    while True:
        try:
            cfg = dwell_mod.load_loop_config()
            if cfg["enabled"]:
                run_cycle()
                time.sleep(max(10, cfg["dwell_s"]))
            else:
                time.sleep(5)
        except Exception:
            time.sleep(10)


# ------------------------------------------------------------ actions

def ping(req):
    cfg = dwell_mod.load_loop_config()
    return {"status": "pong", "enabled": cfg["enabled"],
            "dwell_s": cfg["dwell_s"]}


def status(req):
    cfg = dwell_mod.load_loop_config()
    st = dwell_mod.load_state()
    return {"status": "ok", "enabled": cfg["enabled"],
            "dwell_s": cfg["dwell_s"],
            "last_cycle": st.get("last_cycle"),
            "cycles": st.get("cycles", 0),
            "last_level": st.get("last_level"),
            "last_attention": st.get("last_attention"),
            "queue_depth": dwell_mod.queue_depth(),
            "telegram": notify_mod.status()}


def timeline(req):
    return {"status": "ok",
            "entries": dwell_mod.read_timeline(
                int(req.get("n", 20)))}


def queue(req):
    return {"status": "ok",
            "entries": dwell_mod.queue_entries(
                int(req.get("n", 50)))}


def set_loop(req):
    cfg = dwell_mod.load_loop_config()
    enabled = req.get("enabled", cfg["enabled"])
    dwell_s = int(req.get("dwell_s", cfg["dwell_s"]))
    saved = dwell_mod.save_loop_config(enabled, dwell_s)
    return {"status": "ok", **saved}


def cycle_now(req):
    return run_cycle()


if __name__ == "__main__":
    threading.Thread(target=_loop, daemon=True).start()
    serve("dwell", "atmosphere", PORT,
          {"ping": ping, "status": status,
           "timeline": timeline, "queue": queue,
           "set": set_loop, "cycle_now": cycle_now},
          unknown_fmt="Unknown: {action}")
