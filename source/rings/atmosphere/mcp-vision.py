# --- AI Core service label ---
# Label-Name: vision
# Label-Origin: ai-core-workspace build (Zak/Muse)
# Label-Version: 2
# Label-Does: camera frame grabs — local V4L2/USB cameras discovered
#             on THIS machine, plus any RTSP cameras the owner
#             lists in ~/.config/ai-core/cameras.json
# --- end label ---
#!/usr/bin/env python3
"""Vision Service — grab camera frames.

Ring: atmosphere (outer ring — world-facing, takes the weather).
Runs the shared ring lifecycle: register -> serve -> report health.

Camera discovery (rewritten 2026-11-18): the first version of
this service shipped with a hardcoded map of one household's
RTSP cameras baked into the code — on every other machine it
offered cameras that did not exist and could not see the
webcam in front of it. Cameras are DATA, not code: local
devices are discovered from /sys/class/video4linux, and an
owner's network cameras belong in their own config file.
"""
import base64
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from core.ring_service import serve

PORT = 9103
CACHE_DIR = "/tmp/george_cam"
os.makedirs(CACHE_DIR, exist_ok=True)
CONFIG_PATH = os.path.expanduser("~/.config/ai-core/cameras.json")
SYS_ROOT = "/sys/class/video4linux"


def local_cameras(sys_root=None, dev_root="/dev"):
    """This machine's own cameras: {name: entry} from the
    video4linux tree. The first device also answers to the
    plain name 'webcam' — the name every model reaches for."""
    root = sys_root or SYS_ROOT
    found = {}
    try:
        entries = sorted(os.listdir(root))
    except OSError:
        return found
    for entry in entries:
        device = os.path.join(dev_root, entry)
        if not os.path.exists(device):
            continue
        name = "Webcam"
        try:
            with open(os.path.join(root, entry, "name")) as f:
                name = f.read().strip() or name
        except OSError:
            pass
        # One physical camera often registers TWO nodes with
        # the same name (capture + metadata). Keys must stay
        # unique per node, or the metadata node silently
        # replaces the capture node in the map — the exact
        # failure that made a working webcam 'inappropriate
        # ioctl' on the reference laptop (2026-11-18).
        key = f"webcam ({name})"
        if key in found:
            key = f"webcam ({name} · {entry})"
        found[key] = {"kind": "local", "device": device}
    if found:
        first = next(iter(found.values()))
        found = {"webcam": first, **found}
    return found


def configured_cameras(path=None):
    """The owner's network cameras, from their config file:
    {"name": "rtsp://..."}. Absent or unreadable = none."""
    try:
        with open(path or CONFIG_PATH) as f:
            data = json.load(f)
        return {k: {"kind": "rtsp", "url": v}
                for k, v in data.items() if isinstance(v, str)}
    except Exception:
        return {}


def camera_map(sys_root=None, path=None, dev_root="/dev"):
    """Configured cameras first, local discovery last — so the
    plain 'webcam' always means the camera on THIS machine."""
    merged = configured_cameras(path)
    merged.update(local_cameras(sys_root, dev_root))
    return merged


def _ffmpeg_error(r):
    tail = (r.stderr or "").strip().splitlines()
    return tail[-1] if tail else f"ffmpeg exited {r.returncode}"


def _try_grab(cmd, outpath, runner):
    # A frame counts only if THIS run produced it — a stale
    # file at the same path once let a dead node 'succeed'.
    try:
        os.remove(outpath)
    except OSError:
        pass
    try:
        r = runner(cmd, capture_output=True, text=True,
                   timeout=20)
    except Exception as e:
        return None, f"frame grab could not run: {e}"
    if os.path.exists(outpath) and os.path.getsize(outpath) > 1000:
        with open(outpath, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return {"path": outpath, "base64": b64[:200] + "...",
                "size": os.path.getsize(outpath)}, None
    return None, _ffmpeg_error(r)


def grab_frame(camera_name, cmap=None, runner=subprocess.run):
    """Grab a single frame from a discovered or configured
    camera. Failures name the actual cause — a silent empty
    result once hid a broken ffmpeg for a whole evening. The
    plain 'webcam' tries each local node in turn: sibling
    nodes of one camera are not all capture-capable."""
    cmap = cmap if cmap is not None else camera_map()
    entry = cmap.get(camera_name)
    if not entry:
        known = ", ".join(cmap) or "none"
        return {"status": "error",
                "message": f"Unknown camera: {camera_name}. "
                           f"Cameras here: {known}"}
    outpath = os.path.join(
        CACHE_DIR,
        camera_name.replace("/", "_").replace(" ", "_") + ".jpg")
    if entry["kind"] == "local":
        if camera_name == "webcam":
            candidates = [e for e in cmap.values()
                          if e["kind"] == "local"]
        else:
            candidates = [entry]
        errors = []
        for cand in candidates:
            cmd = ["ffmpeg", "-y", "-f", "v4l2",
                   "-i", cand["device"],
                   "-frames:v", "1", "-s", "640x480",
                   "-update", "1", outpath]
            got, err = _try_grab(cmd, outpath, runner)
            if got:
                return {"status": "ok", "camera": camera_name,
                        "device": cand["device"], **got}
            errors.append(f"{cand['device']}: {err}")
        return {"status": "error",
                "message": f"no frame from {camera_name}: "
                           + "; ".join(errors)}
    cmd = ["ffmpeg", "-y", "-rtsp_transport", "tcp",
           "-i", entry["url"],
           "-frames:v", "1", "-s", "640x480",
           "-update", "1", outpath]
    got, err = _try_grab(cmd, outpath, runner)
    if got:
        return {"status": "ok", "camera": camera_name, **got}
    return {"status": "error",
            "message": f"no frame from {camera_name}: {err}"}


def _session_env():
    """A system service starts with no session environment;
    pulse is unreachable without these (the sound service
    learned this first — same trap, third door)."""
    env = dict(os.environ)
    uid = os.getuid()
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{uid}")
    env.setdefault("DBUS_SESSION_BUS_ADDRESS",
                   f"unix:path=/run/user/{uid}/bus")
    return env


def _pulse_sources(runner=subprocess.run):
    """Named pulse capture sources, for clip audio. The
    default source can be an empty port while the real
    mic sits on a named one (the laptop lesson)."""
    try:
        r = runner(["pactl", "list", "short", "sources"],
                   capture_output=True, text=True, timeout=5,
                   env=_session_env())
        return [p.split("\t")[1] for p in
                (r.stdout or "").splitlines()
                if len(p.split("\t")) >= 2
                and "input" in p.split("\t")[1]
                and not p.split("\t")[1].endswith(".monitor")][:3]
    except Exception:
        return []


def _audio_mean_db(path, runner=subprocess.run):
    """mean_volume of a clip's audio, or None."""
    try:
        r = runner(["ffmpeg", "-i", path, "-af", "volumedetect",
                    "-f", "null", "-"], capture_output=True,
                   text=True, timeout=15, env=_session_env())
        for line in (r.stderr or "").splitlines():
            if "mean_volume" in line:
                raw = line.rsplit(":", 1)[1].strip().split()[0]
                return None if raw == "-inf" else float(raw)
    except Exception:
        pass
    return None


def clip_frame(camera_name, seconds=6, cmap=None,
               runner=subprocess.run):
    """A short A/V clip — the dwell loop's timelapse unit
    (Zak, 2026-11-18: video on a loop, reviewed while
    listening). Local cameras take video from the device
    and audio from the pulse source that actually hears
    (silent audio retries the next source); stream cameras
    carry their own audio. A clip with no working audio
    path still lands, labelled audio: none."""
    cmap = cmap if cmap is not None else camera_map()
    entry = cmap.get(camera_name)
    if not entry:
        known = ", ".join(cmap) or "none"
        return {"status": "error",
                "message": f"Unknown camera: {camera_name}. "
                           f"Cameras here: {known}"}
    outpath = os.path.join(
        CACHE_DIR,
        camera_name.replace("/", "_").replace(" ", "_") + ".mp4")
    try:
        os.remove(outpath)
    except OSError:
        pass
    if entry["kind"] == "rtsp":
        cmd = ["ffmpeg", "-y", "-rtsp_transport", "tcp",
               "-i", entry["url"], "-t", str(seconds),
               "-s", "640x480", "-c:v", "mpeg4", "-c:a", "aac",
               outpath]
        try:
            r = runner(cmd, capture_output=True, text=True, env=_session_env(),
                       timeout=seconds + 25)
        except Exception as e:
            return {"status": "error",
                    "message": f"clip could not run: {e}"}
        if os.path.exists(outpath) \
                and os.path.getsize(outpath) > 5000:
            return {"status": "ok", "camera": camera_name,
                    "path": outpath,
                    "size": os.path.getsize(outpath),
                    "audio": "stream"}
        return {"status": "error",
                "message": f"no clip from {camera_name}: "
                           f"{_ffmpeg_error(r)}"}
    # local: video from the device, audio walked like the
    # sound service walks it — silence retries the next one
    sources = ["default"] + _pulse_sources(runner)
    errors = []
    for src in sources:
        cmd = ["ffmpeg", "-y", "-f", "v4l2",
               "-i", entry["device"],
               "-f", "pulse", "-i", src,
               "-t", str(seconds), "-s", "640x480",
               "-c:v", "mpeg4", "-c:a", "aac", outpath]
        try:
            r = runner(cmd, capture_output=True, text=True, env=_session_env(),
                       timeout=seconds + 12)
        except Exception as e:
            errors.append(f"{src}: could not run ({e})")
            continue
        if not (os.path.exists(outpath)
                and os.path.getsize(outpath) > 5000):
            errors.append(f"{src}: {_ffmpeg_error(r)}")
            continue
        mean = _audio_mean_db(outpath, runner)
        # digital silence measures -inf / below -90; a real
        # room, even a quiet one, sits at -50..-80 — the bar
        # is "measurably above digital zero", not "loud"
        if mean is not None and mean > -85.0:
            return {"status": "ok", "camera": camera_name,
                    "path": outpath,
                    "size": os.path.getsize(outpath),
                    "audio": src, "audio_db": mean}
        errors.append(f"{src}: audio measured silent "
                      f"({mean} dB mean)")
    last_err = "; ".join(errors) or "no audio path ran"
    # video-only last resort — a silent clip beats no clip,
    # labelled for what it is
    cmd = ["ffmpeg", "-y", "-f", "v4l2", "-i", entry["device"],
           "-t", str(seconds), "-s", "640x480",
           "-c:v", "mpeg4", outpath]
    try:
        r = runner(cmd, capture_output=True, text=True, env=_session_env(),
                   timeout=seconds + 25)
        if os.path.exists(outpath) \
                and os.path.getsize(outpath) > 5000:
            return {"status": "ok", "camera": camera_name,
                    "path": outpath,
                    "size": os.path.getsize(outpath),
                    "audio": "none", "audio_note": last_err}
    except Exception:
        pass
    return {"status": "error",
            "message": f"no clip from {camera_name}: {last_err}"}


def list_cameras(cmap=None):
    cmap = cmap if cmap is not None else camera_map()
    return {"status": "ok", "cameras": list(cmap.keys()),
            "count": len(cmap),
            "details": {k: v["kind"] for k, v in cmap.items()}}


def ping(req):
    return {"status": "pong", "service": "vision"}


def list_cams(req):
    return list_cameras()


def grab(req):
    return grab_frame(req.get("camera", ""))


def clip(req):
    return clip_frame(req.get("camera", ""),
                      int(req.get("seconds", 6)))


def grab_all(req):
    cmap = camera_map()
    results = {}
    for name in cmap:
        results[name] = grab_frame(name, cmap)
    return {"status": "ok", "frames": results}


if __name__ == "__main__":
    serve("vision", "atmosphere", PORT,
          {"ping": ping, "list": list_cams, "grab": grab, "grab_all": grab_all, "clip": clip})
