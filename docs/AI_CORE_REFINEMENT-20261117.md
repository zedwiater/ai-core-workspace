# AI Core — refinement lab (begun 2026-11-17)

The Dream (Zak, 2026-11-17, verbatim): "Autonomous AI conduit that brings
competent and relevant AI into any system at any level working with users
to find balanced flow for AI with the hardware aptitude they have
available. Setting expectations and calculating joy along the way."

This folder is where the refinement of Zak's AI Core
(github: zedwiater/ai-core-workspace; local tree at
~/workspace/mint-forensics/ai-edge-node-github, branch geometric-nesting)
is developed before it lands in the repo. The v1 already has the install
planner (source/core/setup.py: detect_profile + sized plans) and a
surface-consistency census (source/core/selfmaint.py). The refinement
adds the runtime half those don't cover:

## Brick 1 — census.py (landed 2026-11-17)

Crawl-time capability census. Stdlib-only, read-only, runs anywhere
Python 3 runs. It measures EFFECTIVE capacity (cgroup quotas where
visible, contention via load), inventories runtimes and models on the
box, derives a parallel-task budget (conversation seat first, pinned;
task seats from what remains), and emits an EXPECTATION TABLE per tier —
expectations.json for a fellow AI user, expectations.md for a human.
Every estimate is labeled and calibrated on the reference install
(Zak's home stack, measured 2026-11-15..17).

Verified runs (runs/): this VM (floor case — no models, script floor
carries it, stated plainly) and Zak's PC (mid case — conversation
correctly read as a pinned GPU+CPU split seat; budget 4 parallel model
tasks; vision + image tiers found on the box).

Known v0 gaps, stated honestly:
- Audio probe understates installs whose whisper lives in a project
  venv rather than the system python (the PC reads "limited"; its
  whisper runs inside the stack's envs).
- tok/s and load-time figures are calibrated estimates, not
  measurements. Brick 2 is a --measure mode: short live probes per
  seat that replace estimates with receipts.
- GPU enumeration lists every DRM node; the budget uses the largest
  VRAM, which matched the reference box.

## Brick 1.5 — pipes.py (landed 2026-11-17, Zak's direction)

The pipe registry + recognizer. The registry is the software version of
the reference install's pipes — RTSP cam mains/subs/slow-grabs, USB
webcam/mic, the parallel audio ear, whisper-class STT, TTS, the model
doors, the VL door, image generation, MQTT, the phrase router — each
with its MEASURED reference timings (roam probe 2026-11-16; VL/image
receipts 2026-11-17) and the doctrine that travels with it. The
recognizer probes a box, matches found pipes to the registry, marks
each as a feed to a named plugin, and assigns a lane from performance
(LIVE / PREQUEUE with lead / FALLBACK-to-sub / PARALLEL for audio /
PARKED / ON-DEMAND / SERVICE). From the feeds present it derives the
SCRIPT-TIER OFFERS — the quick-action pipes those feeds make possible
(camera scripts, voice commands, say-it, dwell sight, graphics,
emergency alerts). Unrecognized listeners are listed, never dropped;
unfound registry pipes are not promised.

Proven on the reference PC: 11 pipes recognized (incl. STT and TTS,
found by an env-aware probe that reads the pythons named in the
install's own service definitions — faster_whisper and edge_tts live in
the stack's venv, invisible to the system python), 4 script tiers
offered. Known scope limit: the recognizer is box-local in v0 — the
camera feeds ride a relay on a second host (the Pi), so the RTSP pipes
read "not found" on the PC itself; a production census also reads the
relay's config/API for network feeds. The VL door reads found only
while seated, which is correct for an on-demand organ.

## Brick 2 — bifurcation cloning: edge kit + conduit (landed 2026-11-17)

Zak's final option: the app subdivides itself, carrying the same DNA to
edge nodes. edge/bundle/ is the shippable kit (census.py + pipes.py +
websearch.py + edge_report.py, stdlib-only); a node runs its own census
and emits ONE report (the snap report pipe) to the conduit.
edge/conduit.py reads all node reports and produces the tab model
(tabs.json — one tab per node + the UNITED wonder-twin tab), rule-based
advisories (the return leg), and task placement. edge/node_social.py
renders the hourly dwell social (5-minute read: system, connections,
stability, progress + conduit advice).

First live system (2026-11-17, nodes/): PC (4 seats, 12 pipes), Pi 5
(ARM, 1 seat, 4 pipes — it already shelves qwen2.5:3b/1.5b, gemma3:1b,
tinyllama), this VM (1 seat, 2 pipes). United: 6 model seats; vision
and image generation are PC single-points. Hardware-limit finding: the
Pi's load is chronically ~11-12 on 4 cores (the standing 'Pi saturated'
ruling) — its seat is nominal; cooperation means the conduit places
compute on the PC, sensing/reporting on the Pi, and degrades honestly
past the system total. Advisory engine caught exactly that on cycle 1.
Not yet mechanized: the hourly timer (one unit file when Zak says go),
the backbone/back-channel auto-setup in the installer, and the GTK tab
rendering (tabs.json is its data model).

## Next bricks ( Zak's basement feedback feeds the order)

1. census --measure: replace estimates with measured seat timings.
2. The announcement/heartbeat protocol as a core convention (the
   status.json pattern from the graphics hand, generalized): any seat
   taken is announced, any long task streams state, a silent hang is
   a bug state with a watcher, never a UX.
3. Census → tier-ring formation: the table becomes the plan the
   initializer executes (drop-in shaped for source/core/).
4. Joy calculation hooks: expectation-vs-experience logging per task
   (promised class vs felt class), the raw material of the Joy
   Calculator at runtime.

## Brick 3 — the conduit hub + bilateral disconnect (landed 2026-11-17)

edge/disconnect.py severs the pipes from their ad-hoc arrangement into
the CONDUIT: snapshot (arrangement as found) -> adopt (hub registry in
conduit/state/hub.json — every pipe with path, process location,
metrics source and tier; tier-categorized log trails in conduit/logs/)
-> release (verify against snapshot, archive, hand back). Adoption is
registry-level by design: the conduit hosts the map, metrics, routing
and logs while processes keep flowing underneath (the stability rule);
a literal traffic cutover is a separate gated step. The hub app
(app/conduit-app.html, baked by app/make_data.py) renders it: node
tabs + united view, system map, process directory, tier logs,
Simple/Advanced/Custom views, searchable Help & Glossary.

## Brick 3.5 — hub watch (landed 2026-11-17)

edge/hub_watch.py is the hub's active crawl: hourly diff of ports,
devices and service units against the node's baseline, plus a
known-services table (Frigate, MediaMTX/go2rtc, Ollama, MQTT, Home
Assistant). New arrivals get integration suggestions with linking
options — web-UI link card, credential POINTER (where the login lives;
never the secret), feed hookup. Identity is process-confirmed, not
port-only (a bare :5000 once claimed Frigate on a box running none).
Hourly hub-watch.timer runs on the PC and Pi 5; the VM's watch rides
the conduit cycle (no user systemd bus in its sandbox).
