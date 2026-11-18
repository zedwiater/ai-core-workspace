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
import os
import re
import subprocess
import sys
import time
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


def check_microphone(seconds=2):
    """Record a short clip and try to transcribe it for keyword spotting.
    Returns the transcribed text or empty string."""
    try:
        clip = f"/tmp/george_listen_{int(time.time())}.wav"
        # Record 2 seconds of audio
        r = subprocess.run([
            "ffmpeg", "-y", "-f", "alsa", "-i", "default",
            "-t", str(seconds), "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1", clip
        ], capture_output=True, text=True, timeout=10)

        if not os.path.exists(clip) or os.path.getsize(clip) < 1000:
            return ""

        # Use local whisper if available, otherwise skip
        try:
            import whisper
            model = whisper.load_model("tiny")
            result = model.transcribe(clip)
            os.remove(clip)
            return result.get("text", "")
        except ImportError:
            os.remove(clip)
            return ""
    except:
        return ""


def ping(req):
    return {"status": "pong", "listening": LISTENING,
            "cooldown": COOLDOWN_UNTIL is not None}


def listen(req):
    """Listen for a few seconds and report what was heard"""
    global COOLDOWN_UNTIL
    text = check_microphone(req.get("duration", 2))

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
    return {
        "status": "ok",
        "listening": LISTENING,
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
