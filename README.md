# ai-core-workspace

## What this actually is

AI Core is a self-contained tool that captures and creates a
**usage-and-function DNA** for AI models.

Every AI you can download starts out generic — the same weights
for everybody. What makes one installation *yours* is not the
model. It is the accumulated record of how it is actually used:
**usage stats, prompt/response results, and joy calculations**,
transduced on the backend into one growing record. That record
entangles three things that are usually kept separate — **the
user, the system, and the models** — into a single identity:

- At install, the identity is minted like a **birth
  certificate**: from your own answers (the Joy Calculator),
  your chosen agreement, and your machine's honest census.
- Through use, it grows like a **passport**: every real change —
  a tier moving, a sense arriving, the system's relevance
  drifting far enough to matter — is recorded, witnessed, and
  stamped in.
- Over usage time, that history is continually **compressed and
  vectorized** toward a functional matmul that carries the
  history with it — an AI that can expand and build itself and
  its relationship, relevant and functional to its reality and
  its end user, because the acceleration is made of *their*
  life, not of generic data.

**How long usage takes to evolve into functional matmul is
individual and unknown.** There is no schedule and no promise
of one. The design only guarantees the direction: use becomes
DNA, DNA becomes history, history becomes the matmul — at
whatever pace a real life supplies the deltas.

The design is written down in full:
[docs/BIRTH-CERTIFICATE-PASSPORT.md](docs/BIRTH-CERTIFICATE-PASSPORT.md).

**Privacy is structural, not a policy.** The DNA — the
certificate, the passport, the record it is measured
against — is **local only**. It never leaves the machine it
was born on: not in this repo, not in a backup that ships,
not as telemetry. What this repo ships is the *machinery*.
Each install mints its own DNA locally, from its own user,
on its own hardware. The DNA is never downloaded; it is born
where it lives.

---

## What it is today

A GTK4 desktop client that plugs your local Ollama models
directly into your system. Not a chat wrapper — it's an
**Intercept & Compute cycle** that lets AI run commands, read
files, analyze cameras, and manage your machine through 8 MCP
micro-services running as background sockets.

Built because cloud APIs are expensive and local models are
good enough. Runs completely offline.

The conduit underneath the DNA design already stands: a
hardware census that sizes the install honestly, model tiers
from a script floor (no model at all) up through seated local
models, a dwell loop that patrols and reviews what the house
shows it, an SOS minimum that keeps the core logic alive
through failure, and the Joy Calculator circuit the identity
is minted from. The DNA → passport → matmul path above is
the trajectory this machinery is built for — designed,
recorded, and being lived into on the author's own machines.
The matmul end of it is not claimed as built.

---

## What It Does

You type something into the chat window. The model thinks. If it needs to do something — run a command, read a file, grab a camera frame, execute code, store memory — it emits a structured tool token. The client catches it, routes it to the MCP service, and feeds the result back. Loop repeats up to 5 times, then the model gives a final answer.

**Attach an image** and the client auto-routes through LLaVA 7B for vision analysis — no manual model switching needed.

No API keys. No internet required. Just Ollama on localhost:11434.

---

## v1 (2026-11-13) — the full app

The client grew its doors, all behind a calm main surface:

- **Joy Calculator + themes** — a short agree/disagree instrument
  sets the relationship depth (L1–L5); the depth becomes the
  standing theme on open. The **base floor** checks all 8 services
  on wake and on a 15-minute dwell — alignment monitors only on
  those beats, in every theme.
- **Options** — patience, cadence scaling, senses, redundancy and
  cloud posture, each choice with its cost on its face, persisted
  through the memory service.
- **Models** — per-slot stacks (chat / reason / summarizer):
  Ollama discovery or any OpenAI-compatible endpoint; the first
  reachable entry the standing policy allows serves, and says so.
- **Learn** — the back story and the technical receipts, in three
  reading layers; the same layers drive every explainer tooltip.
- **Setup** — a plan-first bootstrap for a fresh Linux box:
  read-only inspection, cost announced up front, a privilege
  comfort gradient (no silent sudo), home-folder-minimum mode,
  hardware-sized local models, SSH pairing, guided chat doors.
- **Self-maintenance** — on the floor's beats the app censuses
  its own declared surfaces, repairs the mechanical with backups
  and receipts, and files the rest as proposals for the owner's
  red pen. New services join by **label + route** only.
- **Parent / daughter hybrid** — one install can run as a parent,
  a sensing daughter (hash-chained briefs, no raw media), or both.
- **The Eddy Toy** — a small un-harnessed pond. Poke it.

Instructions live twice: `docs/INSTRUCTIONS_PLAIN.md` for humans,
`docs/INSTRUCTIONS_AI.md` as an executable spec for agents. The
design record is `docs/APP_EXPERIENCE_AND_HARNESS.md`; the
geometry is `docs/GEOMETRIC_NESTING.md`. Tests:
`python3 -m unittest discover -s tests -t .` (119 checks).

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
for f in source/rings/*/mcp-*.py; do python3 "$f" &; done

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
TOOL:vision:grab:{"camera":"<name>"}
TOOL:vision:list:{}
TOOL:memory:set:{"key":"<name>","value":"<data>"}
TOOL:memory:get:{"key":"<name>"}
TOOL:memory:list:{}
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
├── docs/
│   └── GEOMETRIC_NESTING.md    # Why the tree is shaped this way
├── source/
│   ├── app/
│   │   └── ai-client.py        # GTK4/Libadwaita client (chat + Joy Calculator tab)
│   ├── core/                   # The balanced center — shared by everything
│   │   ├── protocol.py         # TOOL: tokens, wire format, socket caller
│   │   ├── ring_service.py     # The register→serve→report-health lifecycle
│   │   ├── loop.py             # The Intercept & Compute tool loop
│   │   └── intake.py           # Joy Calculator engine (relationship depth)
│   ├── rings/
│   │   ├── state/              # Inner ring — holds state
│   │   │   ├── mcp-memory.py   # SQLite key-value store (9108)
│   │   │   └── mcp-coding.py   # Python code execution (9107)
│   │   ├── actuation/          # Middle ring — acts on the machine
│   │   │   ├── mcp-files.py    # Read/write/search files (9101)
│   │   │   └── mcp-shell.py    # Shell execution (9104)
│   │   └── atmosphere/         # Outer ring — world-facing
│   │       ├── mcp-web.py      # Fetch + HTML extract (9102)
│   │       ├── mcp-vision.py   # 9 RTSP cameras (9103)
│   │       ├── mcp-sound.py    # Wake word + alarm detection (9105)
│   │       └── mcp-voice.py    # TTS via edge-tts/espeak (9106)
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
---

## AI Core refinement — the conduit release (2026-11-17)

**The one-line test (Zak, 2026-11-18):** this app should give any
bare minimum and up hardware and user AI that is relevant to them
and the environment. Every feature answers to that line.

A day's measured work on top of v1, proven live on a three-node home
system (PC + Pi 5 + low VM) before it was pushed. The promise: drop the
core on any hardware and it crawls what it actually has, publishes an
honest per-tier expectation table, and subdivides itself across the
user's machines under one conduit — with receipts, not vibes.

- **source/core/census.py** — effective-capacity crawl (quotas, not
  spec sheets) -> parallel-task budget + expectation table.
- **source/core/pipes.py** — pipe registry + recognizer; measured
  lanes (LIVE / PREQUEUE / FALLBACK / PARALLEL / PARKED / ON-DEMAND /
  SERVICE); script-tier offers from feed combinations.
- **source/core/websearch.py** — free-tier web leg with an expectation
  explainer on every run. Low tier is a tier, not a handicap.
- **source/core/edge/** — the bifurcation kit: `edge_report.py` (a
  node grades itself, emits one snap report), `conduit.py` (tab
  model, advisories, placement, hardware limit), `node_social.py`
  (hourly dwell-social digest), `disconnect.py` (bilateral
  snapshot/adopt/release into the hub; tier log trails),
  `hub_watch.py` (active crawl-diff; integration suggestions with
  web-UI link cards and credential pointers — never secrets).
- **docs/BENCH-20261117.md** — the low/mid proofs: divided workload,
  contention behavior, ETA honesty (predicted 14.6s, measured 14.6s).
- **docs/conduit-app/** — the conduit hub UI prototype (baked by
  make_data.py): node tabs, system map, process directory, tier logs,
  Simple/Advanced/Custom views, searchable help + glossary.

First united system: 6 model seats across 3 nodes; vision and image
generation named as single points; the saturated edge node advised by
the conduit from its own report. Full narrative:
docs/AI_CORE_REFINEMENT-20261117.md.

**Addendum (2026-11-17, evening):** the conduit surface moved into
the desktop client itself — `source/app/conduit_pages.py` renders
the crawl as the client's landing (simple view first), with Joy
Gradient, Nodes, Dwell, Roam Watch (with clickable service doors)
and Help & Support tabs. The installer merges with owner-tuned
systems instead of overwriting them (see
docs/INSTALL-REFINEMENT.md), existing models are advised on via a
first-launch popup — never pulled over — and the landing carries
plain-language switches for the script behaviors. The
docs/conduit-app prototype remains as the design study it was.

## Install (one command)

```bash
curl -fsSL https://raw.githubusercontent.com/zedwiater/ai-core-workspace/geometric-nesting/get.sh | bash
```

The installer is the base function, narrated: it measures the
hardware aptitude, pairs it with a known model, installs and
layers that model, merges with (never overwrites) a tuned system
already in place, and deploys the app — which opens on the crawl,
rendered as its landing page. Supported surface: Linux with
systemd and GTK 4 / libadwaita, from a small laptop (where the
pairing honestly steps down and the script floor leads) to a GPU
workstation. The crawl contract (expectations + pairing, as JSON)
is written for AI readers as much as human ones: any agent can
read what a node promises before asking it for work.

## When something breaks

docs/REPAIRS.md is the repairs glossary: every failure this app
has had in the field, its cause (proven, or suspected and labeled
as such), the exact repair commands, and the prevention now built
in — written to be executed verbatim by a human, a shell, or an
AI. Start there before improvising.
