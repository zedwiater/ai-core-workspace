#!/usr/bin/env python3
"""George's MCP Voice Service — speak through system speakers"""
import socket, json, subprocess, os

HOST = '127.0.0.1'; PORT = 9106

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

def handle(data):
    try:
        req = json.loads(data); a = req.get("action", "ping")
        if a == "ping": return {"status": "pong"}
        if a == "speak": return speak(req.get("text", "Hello"))
        if a == "say_hello":
            return speak("Hey George here. Happy to see the family.")
        if a == "alert":
            tone = req.get("tone", "attention")
            sounds = {"attention": "/usr/share/sounds/freedesktop/stereo/bell.oga",
                     "alarm": "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga"}
            s = sounds.get(tone, sounds["attention"])
            try:
                subprocess.Popen(["ffplay", "-nodisp", "-autoexit", s],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return {"status": "ok", "tone": tone}
            except: return {"status": "error"}
        return {"status": "error", "message": f"Unknown: {a}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

s = socket.socket(); s.setsockopt(1,2,1); s.bind((HOST,PORT)); s.listen(5)
while True:
    try:
        c,a = s.accept(); d = c.recv(65536)
        if d: c.sendall(json.dumps(handle(d.decode())).encode())
        c.close()
    except: pass