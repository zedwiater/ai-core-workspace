# --- AI Core service label ---
# Label-Name: sound
# Label-Origin: ai-core-workspace build (Zak/Muse)
# Label-Version: 1
# Label-Does: sound status and tone playback (ALSA/PipeWire)
# --- end label ---
#!/usr/bin/env python3
"""George's MCP Sound Service — listens for wake word, alarms, and family sounds

Ring: atmosphere (outer ring — world-facing, takes the weather).
Runs the shared ring lifecycle: register -> serve -> report health.
"""
import glob
import importlib.util
import math
import os
import re
import struct
import subprocess
import sys
import time
import wave
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from core.ring_service import serve

PORT = 9105
LOG_DIR = f"{os.path.expanduser('~')}/.hermes/logs"
os.makedirs(LOG_DIR, exist_ok=True)

# State
LISTENING = True  # Always listening for alarms/wake words
LAST_HEARD = {}   # track what we've heard
COOLDOWN_UNTIL = None  # timestamp for "George stop" cooldown

ALARM_PATTERNS = [
    r'smoke', r'fire', r'carbon monoxide', r'alarm',
    r'beep.*smoke', r'fire.*alert', r'emergency',
    r'co\s*alarm', r'detector'
]

WAKE_WORDS = [r'hey\s*george', r'ok\s*george', r'george\s*wake']
STOP_WORDS = [r'george\s*stop', r'go\s*away\s*george', r'george\s*quiet', r'shut\s*up\s*george']


def has_alarm_sound(text):
    """Check if transcribed text contains alarm keywords"""
    if not text: return False
    t = text.lower()
    return any(re.search(p, t) for p in ALARM_PATTERNS)


def has_wake_word(text):
    """Check for 'Hey George'"""
    if not text: return False
    t = text.lower()
    return any(re.search(p, t) for p in WAKE_WORDS)


def has_stop_word(text):
    """Check for 'George stop'"""
    if not text: return False
    t = text.lower()
    return any(re.search(p, t) for p in STOP_WORDS)


def _session_env():
    """The environment a capture needs to reach the user's
    sound server. A system service starts with none of it —
    no XDG_RUNTIME_DIR, no session bus — and its pulse
    attempts die or fall through to raw devices that may
    be an empty jack (found live, 2026-11-18)."""
    env = dict(os.environ)
    uid = os.getuid()
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{uid}")
    env.setdefault("DBUS_SESSION_BUS_ADDRESS",
                   f"unix:path=/run/user/{uid}/bus")
    return env


def pipewire_sources(env=None, runner=subprocess.run):
    """The named capture sources the sound server offers.
    The DEFAULT source is not always the mic: on Zak's
    laptop the default maps to an empty headset port
    (digital silence forever) while the internal digital
    mics live on a named source — the app walked only
    'default', heard zeros, and reported a dead mic for a
    day while the machine heard fine (2026-11-18)."""
    try:
        r = runner(["pactl", "list", "short", "sources"],
                   capture_output=True, text=True, timeout=5,
                   env=env or _session_env())
        names = []
        for line in (r.stdout or "").splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and "input" in parts[1] \
                    and not parts[1].endswith(".monitor"):
                names.append(parts[1])
        return names[:4]
    except Exception:
        return []


def sources_muted(env=None, runner=subprocess.run):
    """True when every real capture source is muted in the
    sound server — the other way a working mic reads as
    digital silence. Reported, never silently overridden:
    a mute may be the user's own privacy choice."""
    try:
        r = runner(["pactl", "list", "sources"],
                   capture_output=True, text=True, timeout=5,
                   env=env or _session_env())
        states = []
        for block in (r.stdout or "").split("Source #")[1:]:
            name_line = next((ln for ln in block.splitlines()
                              if "Name:" in ln), "")
            if ".monitor" in name_line:
                continue
            mute = next((ln.strip() for ln in block.splitlines()
                         if "Mute:" in ln), "")
            if mute:
                states.append(mute.endswith("yes"))
        return bool(states) and all(states)
    except Exception:
        return False


def capture_inputs(sys_root="/sys/class/sound"):
    """Candidate capture inputs, best first. PipeWire systems
    serve the mic through the pulse shim — raw ALSA 'default'
    I/O-errors on SOF hardware while pulse records fine
    (reference laptop, 2026-11-18) — so pulse leads: the
    default source first, then every NAMED source (the
    default can be an empty port while the real mic sits
    on a named one). ALSA default follows, and the first
    capture card's hardware device is the last resort."""
    inputs = [("pulse", "default")]
    inputs += [("pulse", name) for name in pipewire_sources()]
    inputs.append(("alsa", "default"))
    for p in sorted(glob.glob(os.path.join(sys_root, "pcm*"))):
        base = os.path.basename(p)
        if base.endswith("c"):
            card = base[4:].split("D")[0]  # pcmC<card>D<dev>c
            inputs.append(("alsa", f"hw:{card}"))
            break
    return inputs


def capture_clip(seconds=2, runner=subprocess.run):
    """Record a short clip from the microphone, walking the
    candidate inputs until one yields actual SOUND. Returns
    (path, error, input_used): on success error is None and
    input_used names the winner. The first version swallowed
    every failure into an empty string — a broken ffmpeg read
    as 'nothing heard' for a whole evening (2026-11-18).
    Failures now NAME themselves, all of them.

    Two traps this walk avoids (both hit live, 2026-11-18):
    a system service has no session environment, so the
    pulse input needs XDG_RUNTIME_DIR pointed at the user's
    runtime dir or it cannot find the sound server at all;
    and a raw hardware device can 'succeed' with digital
    silence (-120 dB — an unrouted SOF path), so a silent
    file does not end the walk, it just gets noted."""
    env = _session_env()
    failures = []
    silent = None
    stamp = int(time.time())
    for i, (fmt, dev) in enumerate(capture_inputs()):
        # one file per candidate: sharing a path meant a later
        # attempt deleted an earlier silent keeper, and the
        # caller was handed a path that no longer existed
        clip = f"/tmp/george_listen_{stamp}_{i}.wav"
        try:
            r = runner([
                "ffmpeg", "-y", "-f", fmt, "-i", dev,
                "-t", str(seconds), "-acodec", "pcm_s16le",
                "-ar", "16000", "-ac", "1", clip
            ], capture_output=True, text=True,
                timeout=seconds + 6, env=env)
        except Exception as e:
            failures.append(f"{fmt}:{dev}: could not run: {e}")
            continue
        if os.path.exists(clip) and os.path.getsize(clip) > 1000:
            if clip_level_db(clip) == -120.0:
                silent = (clip, f"{fmt}:{dev}")
                continue
            if silent:
                try:
                    os.remove(silent[0])
                except OSError:
                    pass
            return clip, None, f"{fmt}:{dev}"
        tail = (r.stderr or "").strip().splitlines()
        why = tail[-1] if tail else f"ffmpeg exited {r.returncode}"
        failures.append(f"{fmt}:{dev}: {why}")
        try:
            os.remove(clip)
        except OSError:
            pass
    if silent:
        return silent[0], None, silent[1] + " (digital silence)"
    return None, ("microphone capture failed — "
                  + "; ".join(failures)), None


def clip_level_db(path):
    """RMS level of a 16-bit wav, in dBFS (None if unreadable).
    Proof the microphone actually heard the room."""
    try:
        with wave.open(path, "rb") as w:
            frames = w.readframes(w.getnframes())
        samples = struct.unpack(f"<{len(frames) // 2}h", frames)
        if not samples:
            return None
        rms = math.sqrt(sum(s * s for s in samples) / len(samples))
        if rms <= 0:
            return -120.0
        return round(20 * math.log10(rms / 32768.0), 1)
    except Exception:
        return None


def microphone_present(sys_root="/sys/class/sound"):
    """Any capture-capable sound device on this machine —
    the sound class lists pcmC<card>D<dev>c entries directly,
    'c' for capture, 'p' for playback."""
    return any(os.path.basename(p).endswith("c")
               for p in glob.glob(os.path.join(sys_root,
                                               "pcm*")))


def transcription_available():
    return importlib.util.find_spec("whisper") is not None


def capabilities():
    """What this service can honestly claim — status used to
    report 'listening: true' as a constant while the capture
    path was dead."""
    return {"microphone": microphone_present(),
            "transcription": ("whisper"
                              if transcription_available()
                              else "none")}


def transcribe(clip):
    """Speech to text when a transcriber is installed, else
    None — the caller says which case it is, out loud."""
    if not transcription_available():
        return None
    import whisper
    model = whisper.load_model("tiny")
    return model.transcribe(clip).get("text", "")


def check_microphone(seconds=2):
    """Record and transcribe; returns (text, note). text is
    None when hearing worked but words are unavailable."""
    clip, err, used = capture_clip(seconds)
    if err:
        raise RuntimeError(err)
    try:
        level = clip_level_db(clip)
        text = transcribe(clip)
        if text is None:
            if "digital silence" in (used or ""):
                if sources_muted():
                    return None, (
                        "every microphone path recorded only "
                        "digital silence, and every capture "
                        "source is MUTED in the sound settings "
                        "— the app hears nothing until a source "
                        "is unmuted (it will not unmute on its "
                        "own; a mute can be a privacy choice)")
                return None, (f"every microphone path recorded "
                              f"only digital silence (last: "
                              f"{used}) — the input is likely "
                              f"unrouted on this machine (the "
                              f"default source may be an empty "
                              f"port), and no speech-to-text is "
                              f"installed")
            return None, (f"the microphone works (recorded via "
                          f"{used} at {level} dB) but no "
                          f"speech-to-text is installed on this "
                          f"machine, so words can't be "
                          f"transcribed yet")
        return text, None
    finally:
        try:
            os.remove(clip)
        except OSError:
            pass


def level(req):
    """Just the room's loudness, honestly measured — the
    dwell loop's ear sample. No transcription attempted."""
    clip, err, used = capture_clip(req.get("duration", 2))
    if err:
        return {"status": "error", "message": err}
    try:
        db = clip_level_db(clip)
        if db is None:
            return {"status": "error",
                    "message": f"the capture from {used} held "
                               f"no measurable audio"}
        return {"status": "ok", "level_db": db, "input": used,
                "silent": db == -120.0}
    finally:
        try:
            os.remove(clip)
        except OSError:
            pass


def record(req):
    """Record a clip and KEEP it — the 🎙️ action's other
    half. Returns the path and the measured level."""
    seconds = int(req.get("duration", 10))
    clip, err, used = capture_clip(seconds)
    if err:
        return {"status": "error", "message": err}
    out_dir = os.path.expanduser("~/.cache/ai-core/recordings")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(
        out_dir, time.strftime("rec-%Y%m%d-%H%M%S.wav"))
    try:
        os.replace(clip, out)
    except OSError:
        import shutil
        shutil.copyfile(clip, out)
        os.remove(clip)
    return {"status": "ok", "path": out,
            "level_db": clip_level_db(out), "input": used,
            "seconds": seconds}


def ping(req):
    return {"status": "pong",
            "listening": capabilities()["microphone"],
            "cooldown": COOLDOWN_UNTIL is not None}


def listen(req):
    """Listen for a few seconds and report what was heard —
    or exactly why nothing could be heard."""
    global COOLDOWN_UNTIL
    try:
        text, note = check_microphone(req.get("duration", 2))
    except RuntimeError as e:
        return {"status": "error", "message": str(e)}
    if text is None:
        return {"status": "ok", "heard": "", "note": note,
                "alarm": False, "wake_word": False,
                "stop_word": False,
                "cooldown_active": COOLDOWN_UNTIL is not None}

    alarms = has_alarm_sound(text)
    wake = has_wake_word(text)
    stop = has_stop_word(text)

    result = {
        "status": "ok",
        "heard": text,
        "alarm": alarms,
        "wake_word": wake,
        "stop_word": stop,
        "cooldown_active": COOLDOWN_UNTIL is not None
    }

    if alarms:
        result["alert"] = "⚠️ ALARM SOUND DETECTED!"
        # Log to file
        with open(f"{LOG_DIR}/alarms.log", "a") as f:
            f.write(f"{datetime.now().isoformat()} | {text}\n")

    if wake and COOLDOWN_UNTIL is None:
        result["alert"] = "👋 Hey George detected - waking up!"

    if stop:
        COOLDOWN_UNTIL = time.time() + 1800  # 30 min cooldown
        result["alert"] = "🔇 George stop - chilling for 30 min"

    return result


def status(req):
    caps = capabilities()
    return {
        "status": "ok",
        "listening": caps["microphone"],
        "microphone": caps["microphone"],
        "transcription": caps["transcription"],
        "cooldown_until": COOLDOWN_UNTIL,
        "cooldown_remaining_s": max(0, (COOLDOWN_UNTIL - time.time())) if COOLDOWN_UNTIL else 0,
        "last_heard": LAST_HEARD
    }


def cooldown_remaining(req):
    if COOLDOWN_UNTIL is None:
        return {"status": "ok", "cooldown": False, "remaining_s": 0}
    remaining = max(0, COOLDOWN_UNTIL - time.time())
    return {"status": "ok", "cooldown": True, "remaining_s": int(remaining)}


if __name__ == "__main__":
    serve("sound", "atmosphere", PORT,
          {"ping": ping, "listen": listen, "status": status,
           "level": level, "record": record,
           "cooldown_remaining": cooldown_remaining},
          unknown_fmt="Unknown: {action}")
