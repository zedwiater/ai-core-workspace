"""Quick Actions — the generalized house hits (Zak's design,
approved 2026-11-18). The phrase router's proven moves, made
universal: show my camera, grab five minutes, say this aloud,
search the web, system status.

Each action names the organ it needs. Availability is checked
honestly and the button SAYS when its organ is absent — a
button that explains beats a button that fails sideways. This
module is the headless engine; the client wires it to buttons.
"""
import os
import shutil
import subprocess
import time

ACTIONS = [
    {"id": "camera", "title": "📷 Show my camera", "organ": "camera",
     "absent": "no camera"},
    {"id": "grab5", "title": "🎞️ Grab five minutes", "organ": "camera",
     "absent": "no camera"},
    {"id": "say", "title": "🔊 Say this aloud", "organ": "voice",
     "absent": "voice service off"},
    {"id": "web", "title": "🔎 Search the web", "organ": "web",
     "absent": "offline"},
    {"id": "status", "title": "🩺 System status", "organ": None,
     "absent": ""},
]

_REASONS = {
    "camera": "no camera was found on this machine — the crawl "
              "checks /dev/video*, and this box reported none",
    "voice": "the voice service isn't answering, so there's "
             "nothing to speak with",
    "web": "the web didn't answer the reachability check — "
           "this one needs the network",
}


def availability(cameras=(), voice_ok=False, web_ok=True):
    """{action_id: (available, reason)} — reason '' when available."""
    organs = {"camera": bool(cameras), "voice": bool(voice_ok),
              "web": bool(web_ok)}
    out = {}
    for a in ACTIONS:
        organ = a["organ"]
        if organ is None or organs.get(organ):
            out[a["id"]] = (True, "")
        else:
            out[a["id"]] = (False, _REASONS[organ])
    return out


def button_label(action, avail):
    """The title, with the absence stated right on the button."""
    ok, _reason = avail.get(action["id"], (True, ""))
    return action["title"] if ok else \
        f"{action['title']} ({action['absent']})"


def cache_dir():
    d = os.path.join(os.path.expanduser("~"), ".cache", "ai-core")
    os.makedirs(d, exist_ok=True)
    return d


def _camera_parts(camera):
    """(device, name) from a census dict OR a bare device
    string. The error path once indexed the argument as a
    dict while handling its own failure — 'never raises'
    has to hold for the argument's shape too."""
    if isinstance(camera, dict):
        return (camera.get("device", ""),
                camera.get("name", "the camera"))
    return str(camera), str(camera)


def camera_still(camera, out_dir=None, runner=subprocess.run):
    """One frame from the camera. (ok, line); never raises."""
    if not shutil.which("ffmpeg"):
        return False, ("ffmpeg isn't installed, so the camera "
                       "can't be read yet — that's the missing "
                       "piece, not the camera")
    device, name = _camera_parts(camera)
    path = os.path.join(out_dir or cache_dir(), "quick-camera.jpg")
    try:
        r = runner(["ffmpeg", "-y", "-f", "v4l2", "-i",
                    device, "-frames:v", "1", path],
                   capture_output=True, timeout=25)
    except Exception as e:
        return False, f"reading {name} failed: {e}"
    if getattr(r, "returncode", 1) == 0 and os.path.exists(path):
        return True, (f"📷 {name} — a frame is saved "
                      f"at {path}")
    return False, (f"{name} didn't give a frame — it "
                   f"may be busy in another app")


def camera_clip(camera, seconds=300, out_dir=None,
                popen=subprocess.Popen):
    """Record a clip in the background. (ok, line); never raises."""
    if not shutil.which("ffmpeg"):
        return False, ("ffmpeg isn't installed, so clips can't "
                       "be recorded yet")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(out_dir or cache_dir(),
                        f"quick-clip-{stamp}.mp4")
    device, name = _camera_parts(camera)
    try:
        popen(["ffmpeg", "-y", "-f", "v4l2", "-i", device,
               "-t", str(seconds), path],
              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
              start_new_session=True)
    except Exception as e:
        return False, f"starting the clip failed: {e}"
    return True, (f"🎞️ Recording {seconds // 60} minutes from "
                  f"{name} → {path} (in the background)")


def system_status(host, threads, ram_free_gb, disk_free_gb,
                  seated, services):
    """The status bubble's lines — pure composition."""
    lines = [f"🩺 {host}: {threads} effective threads, "
             f"{ram_free_gb:.1f} GB of RAM free, "
             f"{disk_free_gb} GB of disk free."]
    lines.append("Seated in Ollama: "
                 + (", ".join(seated) if seated
                    else "nothing right now"))
    lines.append(f"Services: {services}")
    return lines


def web_lines(query, results):
    """Format websearch results for a bubble — pure."""
    if not results:
        return [f"🔎 No results came back for “{query}” — the "
                f"search answered, it just found nothing it "
                f"could show."]
    lines = [f"🔎 {query} — what the web says (leads, not "
             f"verified facts):"]
    for r in results:
        lines.append(f"• {r.get('title', '')}")
        if r.get("snippet"):
            lines.append(f"  {r['snippet']}")
        if r.get("url"):
            lines.append(f"  {r['url']}")
    return lines
