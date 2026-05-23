# ai-core-workspace

A GTK4 desktop client that plugs your local Ollama models directly into your system. Not a chat wrapper — it's an **Intercept & Compute cycle** that lets AI run commands, read files, analyze cameras, and manage your machine through 8 MCP micro-services running as background sockets.

Built because cloud APIs are expensive and local models are good enough. Runs completely offline.

---

## What It Does

You type something into the chat window. The model thinks. If it needs to do something — run a command, read a file, grab a camera frame, execute code, store memory — it emits a structured tool token. The client catches it, routes it to the MCP service, and feeds the result back. Loop repeats up to 5 times, then the model gives a final answer.

**Attach an image** and the client auto-routes through LLaVA 7B for vision analysis — no manual model switching needed.

No API keys. No internet required. Just Ollama on localhost:11434.

---

## The 8 MCP Micro-Services

All run as systemd services, restarted automatically if they crash.

| Icon | Service | Port | What It Does |
|------|---------|------|-------------|
| ⚡ | **Shell** | 9104 | Runs system commands with timeout safety |
| 📁 | **Files** | 9101 | Read, write, and glob-search files |
| 🌐 | **Web** | 9102 | Fetch URLs and extract readable text |
| 👁 | **Vision** | 9103 | Grab RTSP frames from 9 cameras (Pi Wyze Bridge) |
| 🔊 | **Sound** | 9105 | Wake word "Hey George", alarm detection, cooldown |
| 🎤 | **Voice** | 9106 | TTS via edge-tts or espeak, alert tones |
| 💻 | **Coding** | 9107 | Execute Python code with timeout |
| 🧠 | **Memory** | 9108 | Persistent SQLite key-value store |

The sidebar shows live green/red indicators for each service — green means responding, red means down.

---

## Quick Start

```bash
git clone https://github.com/zedwiater/ai-core-workspace.git
cd ai-core-workspace
chmod +x install.sh
sudo ./install.sh
```

Or without installing (just need Ollama):

```bash
# Start MCP services manually
for f in source/mcp/mcp-*.py; do python3 "$f" &; done

# Run the client
python3 source/app/ai-client.py
```

---

## Tool Schemas (for the AI)

When the model emits tool tokens, the client catches them. Full 16-tool set:

```
TOOL:shell:exec:{"cmd":"<command>"}
TOOL:files:read:{"path":"<path>"}
TOOL:files:write:{"path":"<path>","content":"<text>"}
TOOL:files:search:{"pattern":"<glob>","dir":"<dir>"}
TOOL:web:fetch:{"url":"<url>"}
TOOL:web:extract:{"url":"<url>"}
TOOL:vision:capture:{"camera":"<name>"}
TOOL:vision:list_cameras:{}
TOOL:memory:store:{"key":"<name>","value":"<data>"}
TOOL:memory:recall:{"key":"<name>"}
TOOL:memory:list_keys:{}
TOOL:coding:execute:{"code":"<python>"}
TOOL:coding:eval:{"expression":"<expr>"}
TOOL:sound:listen:{"duration":2}
TOOL:voice:speak:{"text":"<phrase>"}
TOOL:voice:alert:{"tone":"attention|alarm"}
```

---

## Project Layout

```
├── install.sh                  # Smart installer (RAM/GPU detection, uninstall)
├── README.md                   # This file
├── source/
│   ├── app/
│   │   └── ai-client.py        # GTK4/Libadwaita client (327 lines)
│   ├── mcp/
│   │   ├── mcp-shell.py        # Shell execution (port 9104)
│   │   ├── mcp-files.py        # Read/write/search files (9101)
│   │   ├── mcp-web.py          # Fetch + HTML extract (9102)
│   │   ├── mcp-vision.py       # 9 RTSP cameras (9103)
│   │   ├── mcp-sound.py        # Wake word + alarm detection (9105)
│   │   ├── mcp-voice.py        # TTS via edge-tts/espeak (9106)
│   │   ├── mcp-coding.py       # Python code execution (9107)
│   │   └── mcp-memory.py       # SQLite key-value store (9108)
│   └── config.json             # Default configuration
```

---

## Uninstall

```bash
sudo ./install.sh uninstall
```

Removes MCP services, desktop entry, and /opt/ai-core. Preserves Ollama models and config.

---

## Requirements

- Python 3.10+
- GTK4 + Libadwaita (for the GUI)
- Ollama running on localhost:11434
- (Optional) ffmpeg for camera frame grabbing
- (Optional) whisper for sound keyword spotting

---

Built with $20 of OpenRouter credits and too many late nights. Because local AI should actually do things, not just chat.