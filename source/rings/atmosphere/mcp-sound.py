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


def capture_clip(seconds=2):
    """Record a short clip from the default microphone.
    Returns (path, error): exactly one of them is set. The
    first version swallowed every failure into an empty
    string — a broken ffmpeg read as 'nothing heard' for a
    whole evening (2026-11-18). Failures now NAME themselves."""
    clip = f"/tmp/george_listen_{int(time.time())}.wav"
    try:
        r = subprocess.run([
            "ffmpeg", "-y", "-f", "alsa", "-i", "default",
            "-t", str(seconds), "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1", clip
        ], capture_output=True, text=True, timeout=15)
    except Exception as e:
        return None, f"capture could not run: {e}"
    if not os.path.exists(clip) or os.path.getsize(clip) < 1000:
        tail = (r.stderr or "").strip().splitlines()
        why = tail[-1] if tail else f"ffmpeg exited {r.returncode}"
        return None, f"microphone capture failed: {why}"
    return clip, None


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
    clip, err = capture_clip(seconds)
    if err:
        raise RuntimeError(err)
    try:
        level = clip_level_db(clip)
        text = transcribe(clip)
        if text is None:
            return None, (f"the microphone works (recorded at "
                          f"{level} dB) but no speech-to-text is "
                          f"installed on this machine, so words "
                          f"can't be transcribed yet")
        return text, None
    finally:
        try:
            os.remove(clip)
        except OSError:
            pass


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
           "cooldown_remaining": cooldown_remaining},
          unknown_fmt="Unknown: {action}")
