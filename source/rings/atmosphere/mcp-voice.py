# --- AI Core service label ---
# Label-Name: voice
# Label-Origin: ai-core-workspace build (Zak/Muse)
# Label-Version: 1
# Label-Does: text-to-speech via espeak-ng / speech-dispatcher
# --- end label ---
#!/usr/bin/env python3
"""George's MCP Voice Service — speak through system speakers

Ring: atmosphere (outer ring — world-facing, takes the weather).
Runs the shared ring lifecycle: register -> serve -> report health.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from core.ring_service import serve

PORT = 9106


def speak(text):
    """Speak text through system speakers using espeak or edge-tts"""
    # Try edge-tts first (better quality)
    try:
        out = f"/tmp/george_speak_{abs(hash(text)) % 10000}.mp3"
        subprocess.run([
            "edge-tts", "--voice", "en-US-AriaNeural",
            "--text", text[:1000], "--write-media", out
        ], capture_output=True, timeout=30)
        if os.path.exists(out):
            subprocess.Popen(["ffplay", "-nodisp", "-autoexit", out],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"status": "ok", "engine": "edge-tts", "file": out, "text": text[:80]}
    except:
        pass

    # Fallback to espeak
    try:
        subprocess.run(["espeak", text[:200]], timeout=10)
        return {"status": "ok", "engine": "espeak"}
    except:
        return {"status": "error", "message": "No TTS engine available"}


def ping(req):
    return {"status": "pong"}


def speak_action(req):
    return speak(req.get("text", "Hello"))


def say_hello(req):
    return speak("Hey George here. Happy to see the family.")


def alert(req):
    tone = req.get("tone", "attention")
    sounds = {"attention": "/usr/share/sounds/freedesktop/stereo/bell.oga",
             "alarm": "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga"}
    s = sounds.get(tone, sounds["attention"])
    try:
        subprocess.Popen(["ffplay", "-nodisp", "-autoexit", s],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"status": "ok", "tone": tone}
    except: return {"status": "error"}


if __name__ == "__main__":
    serve("voice", "atmosphere", PORT,
          {"ping": ping, "speak": speak_action, "say_hello": say_hello, "alert": alert},
          unknown_fmt="Unknown: {action}")
