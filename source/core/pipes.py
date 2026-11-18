#!/usr/bin/env python3
"""pipes.py — AI Core pipe registry + recognizer (refinement brick 1.5,
2026-11-17, Zak's direction).

The conduit needs SOFTWARE versions of the reference install's pipes and
timings. When the census finds an audio or video pipe on a new box, it
should RECOGNIZE it against this registry, mark it as a feed to a named
plugin, and — from the pipe's measured performance — tier or queue it
for speed and quality. From the feeds a box actually has, it should
also offer the custom SCRIPT TIERS (quick-action pipes) those feeds
make possible, the way the reference install's phrase router does.

Registry timings are the reference install's MEASURED numbers (roam hop
probe 2026-11-16 ~23:57, clean python probe; dwell/VL/image receipts
2026-11-17), each labeled with its source. On a new box the recognizer
starts from the reference class and the lane policy below; a --measure
mode (future brick) replaces classes with local receipts.

Lanes (from the roam doctrine):
  LIVE          start <= 0.5s: serve immediately
  PREQUEUE      start <= 6s: pre-queue the next hop so the grab is solid
                on arrival (lead = start + margin)
  FALLBACK      degraded signature: drop to the sub-stream / timelapse+
                audio mode automatically, labeled
  PARALLEL      audio-class: never queued behind video; always-on
  PARKED        unreachable: re-probe on a cycle, never promised live
  ON-DEMAND     a seat, not a stream: announced, capped, heartbeat
  SERVICE       a standing service pipe (bus, NVR, router)

Stdlib only, read-only. Usage: python3 pipes.py [--out DIR]
"""
import glob, json, os, platform, socket, sys, time
import urllib.request

# --- the registry: software versions of the house's pipes -------------------

REGISTRY = [
    # kind, detect, feeds plugin, reference timing profile
    {"id": "rtsp-cam-main", "kind": "video", "name": "Camera main stream (RTSP via relay)",
     "detect": {"mediamtx_path": True},
     "feeds": "vision/roam",
     "reference": {"start_s": 3.6, "quality": "can degrade: low effective fps, audio stall",
                   "source": "livingroom main, roam probe 2026-11-16"},
     "degraded_rule": "on degrade signature, fall to rtsp-cam-sub automatically"},
    {"id": "rtsp-cam-sub", "kind": "video", "name": "Camera sub stream (RTSP via relay)",
     "detect": {"mediamtx_path": True},
     "feeds": "vision/roam",
     "reference": {"start_s": 0.8, "quality": "solid, carries audio",
                   "source": "livingroom_sub, roam probe 2026-11-16"}},
    {"id": "rtsp-cam-slow", "kind": "video", "name": "Camera stream, slow grab (marginal link)",
     "detect": {"mediamtx_path": True},
     "feeds": "vision/roam",
     "reference": {"start_s": 5.3, "audio_start_s": 3.6,
                   "quality": "solid once grabbed; frame corruption possible",
                   "source": "hillbilly_front, roam probe 2026-11-16"}},
    {"id": "usb-webcam", "kind": "video", "name": "USB webcam (V4L2)",
     "detect": {"dev_video": True},
     "feeds": "vision/local-feed",
     "reference": {"start_s": 0.1, "quality": "solid, local",
                   "source": "basement Brio, roam probe 2026-11-16"},
     "note": "prefer the LOCAL pull; the same feed via a relay round-trip has a known stall pattern (basement leg, 2026-11-17)"},
    {"id": "frigate-nvr", "kind": "service", "name": "Frigate NVR (archive truth)",
     "detect": {"http": ("127.0.0.1", 8971, "/api/version")},
     "feeds": "archive/segsearch",
     "reference": {"quality": "records continuously; segments can carry timestamp damage — file-direct playback is the dependable lane, the portal player is strict",
                   "source": "portal playback finding 2026-11-17"}},
    {"id": "rtsp-audio-parallel", "kind": "audio", "name": "Per-feed audio pull (parallel ear)",
     "detect": {"mediamtx_path": True},
     "feeds": "hearing/mic-watch",
     "reference": {"bitrate_kbps": "16-64", "freshness": "seconds",
                   "source": "mic_watch, all night 2026-11-16/17 at load ~0.4-1.1/16 cores"},
     "doctrine": "audio stays parallel — lock phrase, attention and emergency never wait for the video patrol"},
    {"id": "usb-mic", "kind": "audio", "name": "USB microphone (ALSA)",
     "detect": {"alsa_card": True},
     "feeds": "hearing/stt-front-end",
     "reference": {"source": "Brio mic, ALSA card on the reference PC"}},
    {"id": "stt-whisper", "kind": "audio", "name": "Speech-to-text (whisper-class)",
     "detect": {"python_module_any": ["whisper", "faster_whisper"]},
     "feeds": "hearing/transcription",
     "reference": {"timing": "seconds per phrase leg on CPU",
                   "source": "mic_watch legs (faster_whisper in the stack's own venv), reference install"},
     "note": "env-aware probe: the module is looked for in the pythons the install's own services run, not just the system python"},
    {"id": "tts", "kind": "audio", "name": "Text-to-speech",
     "detect": {"any_binary": ["espeak-ng", "edge-tts", "say"],
                "python_module_any": ["edge_tts"]},
     "feeds": "voice/say",
     "reference": {"source": "reference voice is a cloud TTS (Edge, en-AU-NatashaNeural) — cloud caveat travels with the pipe; local engines are the offline fallback"}},
    {"id": "go2rtc-local", "kind": "video", "name": "go2rtc local stream gateway",
     "detect": {"ports_any": [8554, 8556, 1984]},
     "feeds": "vision/local-pull",
     "reference": {"source": "ships inside Frigate on the reference install; the PC-local pull is the standing candidate fix for relay round-trip stalls (basement leg)"}},
    {"id": "ollama-door", "kind": "model", "name": "Ollama model door",
     "detect": {"http": ("127.0.0.1", 11434, "/api/tags")},
     "feeds": "brains/conversation+deep",
     "reference": {"timing": "resident brain ~4.5 tok/s mixed GPU/CPU on the reference box",
                   "source": "george-14, measured 2026-11-15..17"}},
    {"id": "llama-door", "kind": "model", "name": "llama.cpp server door",
     "detect": {"ports_any": [8090, 8091]},
     "feeds": "brains/chat+router tiers",
     "reference": {"timing": "own-door 7B chat ~7.5 tok/s CPU; shared router door carries deep/background tiers",
                   "source": "george-chat :8091 / router :8090, measured 2026-11-15..17"}},
    {"id": "vl-door", "kind": "model", "name": "Vision-language door (on-demand seat)",
     "detect": {"ports_any": [8092]},
     "feeds": "vision/dwell-sight",
     "reference": {"seat_s": "24-34 per 5-frame clip review", "cap_s": 300,
                   "source": "george-vl, measured 2026-11-17"},
     "doctrine": "dwell-only call; the seat is capped and the door closes itself — a specialized model is never left loaded in front of the user"},
    {"id": "image-gen", "kind": "generation", "name": "Image generation (diffusers-class, CPU lane)",
     "detect": {"path_exists": "~/george-lab/imgvenv"},
     "feeds": "hands/graphics",
     "reference": {"timing": "512x512, 20 steps ≈ 63s on the reference CPU", "heartbeat_s": 10,
                   "watcher": "stale >180s alert, >600s stop",
                   "source": "make_image.py first picture, 2026-11-17"},
     "doctrine": "no timeout on generation; a watcher distinguishes working from frozen — silence is never the status"},
    {"id": "mqtt-bus", "kind": "service", "name": "MQTT bus (event stamps)",
     "detect": {"ports_any": [1883]},
     "feeds": "events/slaps",
     "reference": {"source": "frigate-mosquitto on the reference install"}},
    {"id": "web-search", "kind": "knowledge", "name": "Free-tier web search (script leg)",
     "detect": {"https_reachable": "lite.duckduckgo.com"},
     "feeds": "knowledge/web-lookup",
     "reference": {"timing": "fetch 1.1-1.9s on the low VM; answers at network speed, not model speed",
                   "source": "websearch.py first runs, 2026-11-17"},
     "doctrine": "snippets are leads, not verified facts — opening a page is the verification step; conditions data rides wttr.in-class sources, DDG snippets carry none (measured 2026-11-15). Offline, the tier answers from stored model knowledge + system state and says so — narrower, never useless"},
    {"id": "script-router", "kind": "control", "name": "Deterministic phrase router (script tier)",
     "detect": {"path_exists": "~/george-lab/loops/phrase_router.py"},
     "feeds": "control/quick-actions",
     "reference": {"timing": "sub-second to seconds; no model in the loop",
                   "source": "phrase_router, reference install"},
     "doctrine": "exact actions ride scripts, never model improvisation; route candidates from learning never auto-activate"},
]

# Reference instances: the actual fleet, with measured starts and the
# lane each one earned. A new install's census starts from these classes.
REFERENCE_INSTANCES = [
    {"name": "thingpan2", "pipe": "rtsp-cam-main", "start_s": 0.0, "lane": "LIVE"},
    {"name": "livingroom_sub", "pipe": "rtsp-cam-sub", "start_s": 0.8, "lane": "LIVE",
     "note": "fallback target for the degraded main"},
    {"name": "livingroom (main)", "pipe": "rtsp-cam-main", "start_s": 3.6, "lane": "FALLBACK",
     "note": "degraded signature: ~2.4 fps effective, audio stall >30s → sub stream"},
    {"name": "hillbilly_front", "pipe": "rtsp-cam-slow", "start_s": 5.3, "lane": "PREQUEUE",
     "prequeue_lead_s": 8},
    {"name": "basement (Brio, local)", "pipe": "usb-webcam", "start_s": 0.1, "lane": "LIVE"},
    {"name": "thinginov3", "pipe": "rtsp-cam-main", "start_s": None, "lane": "PARKED",
     "note": "no stream; re-probed once per patrol cycle"},
]

# --- lane policy ---------------------------------------------------------------

def lane_for(entry, found):
    if not found:
        return "—"
    kind = entry["kind"]
    if kind == "audio":
        return "PARALLEL" if entry["id"] == "rtsp-audio-parallel" else "SERVICE"
    if kind in ("service", "control", "knowledge"):
        return "SERVICE"
    if entry["id"] in ("vl-door", "image-gen"):
        return "ON-DEMAND"
    if kind == "model":
        return "SERVICE"
    start = entry.get("reference", {}).get("start_s")
    if start is None:
        return "LIVE"
    if start <= 0.5:
        return "LIVE"
    if start <= 6.0:
        return "PREQUEUE"
    return "FALLBACK"

# --- probes ---------------------------------------------------------------------

def listening_ports():
    ports = set()
    for f in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            for line in open(f).read().splitlines()[1:]:
                parts = line.split()
                if parts[3] == "0A":  # LISTEN
                    ports.add(int(parts[1].split(":")[1], 16))
        except Exception:
            pass
    return ports

def http_ok(host, port, path):
    """Any HTTP response — including 400/401/403 from an auth layer —
    proves the pipe is alive. Silence is the only 'absent'."""
    try:
        with urllib.request.urlopen(f"http://{host}:{port}{path}", timeout=2) as r:
            return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False

def candidate_pythons():
    """The pythons an install actually runs: this one, the ones named in
    the user's own service definitions, and common venv locations. The
    conduit reads the install's own wiring instead of assuming the
    system python carries the stack's modules."""
    import re
    cands = [sys.executable]
    for unit in glob.glob(os.path.expanduser("~/.config/systemd/user/*.service")):
        try:
            for m in re.findall(r"(/[^\s\"']*/bin/python3?)", open(unit).read()):
                if m not in cands:
                    cands.append(m)
        except Exception:
            pass
    for pat in ("~/george-lab/*/bin/python3", "~/.venv/bin/python3",
                "~/venv/bin/python3"):
        for p in glob.glob(os.path.expanduser(pat)):
            if p not in cands:
                cands.append(p)
    return cands[:8]

def py_has_any(mods):
    import subprocess
    for py in candidate_pythons():
        for mod in mods:
            try:
                if subprocess.run([py, "-c", f"import {mod}"],
                                  capture_output=True, timeout=6).returncode == 0:
                    return True
            except Exception:
                pass
    return False

def tcp_open(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except Exception:
        return False

def mediamtx_paths():
    """Local MediaMTX API (:9997) path list, if a relay runs on THIS box."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:9997/v3/paths/list",
                                    timeout=2) as r:
            data = json.loads(r.read().decode())
        return [p["name"] for p in data.get("items", [])]
    except Exception:
        return None

def detect(entry, ctx):
    d = entry["detect"]
    if "ports_any" in d:
        return any(p in ctx["ports"] for p in d["ports_any"])
    if "http" in d:
        host, port, path = d["http"]
        return http_ok(host, port, path)
    if "dev_video" in d:
        return bool(glob.glob("/dev/video*"))
    if "alsa_card" in d:
        try:
            return "USB" in open("/proc/asound/cards").read()
        except Exception:
            return False
    if "python_module_any" in d and py_has_any(d["python_module_any"]):
        return True
    if "python_module" in d:
        return py_has_any([d["python_module"]])
    if "any_binary" in d:
        import shutil
        return any(shutil.which(b) for b in d["any_binary"])
    if "path_exists" in d:
        return os.path.exists(os.path.expanduser(d["path_exists"]))
    if "mediamtx_path" in d:
        return ctx["relay_paths"] is not None
    if "https_reachable" in d:
        try:
            req = urllib.request.Request(f"https://{d['https_reachable']}/",
                                         headers={"User-Agent": "ai-core-pipes/0.1"})
            with urllib.request.urlopen(req, timeout=5) as r:
                return True
        except urllib.error.HTTPError:
            return True
        except Exception:
            return False
    return False

# --- script tiers offered by feed combinations -----------------------------------

SCRIPT_TIER_OFFERS = [
    {"needs": ["vision/roam", "archive/segsearch"], "offer": "quick-action camera scripts",
     "scripts": ["show-cam", "grab-last-five", "timelapse", "find-clips"],
     "basis": "cam feeds + NVR archive: the reference install's router serves these deterministically in seconds"},
    {"needs": ["hearing/stt-front-end", "hearing/transcription"], "offer": "voice quick commands",
     "scripts": ["lock phrase", "wake-mode router (router/full)", "voice record start/stop"],
     "basis": "a mic pipe + STT: commands ride scripts, the model is not in the loop"},
    {"needs": ["voice/say"], "offer": "say-it pipes",
     "scripts": ["say in room", "announce"],
     "basis": "a speech pipe exists: announcements are one script call, announced seats included"},
    {"needs": ["vision/dwell-sight", "vision/roam"], "offer": "dwell sight reviews",
     "scripts": ["clip-chunk VL review (dwell-called, seat-capped)"],
     "basis": "a VL door + cam feeds: sight is a capped organ call inside dwell, never a resident greeter"},
    {"needs": ["hands/graphics"], "offer": "graphics hand",
     "scripts": ["make-image (no timeout, watcher-supervised)"],
     "basis": "an image pipe exists: generation runs in the slow lane with a heartbeat, never a silent hang"},
    {"needs": ["events/slaps"], "offer": "emergency alert pipe",
     "scripts": ["emergency class → message alert, deduped"],
     "basis": "an event bus exists: emergency classes get a guaranteed, deduped alert path"},
    {"needs": ["knowledge/web-lookup"], "offer": "ask-the-web quick actions",
     "scripts": ["web search with expectation explainer", "conditions lookup (wttr.in-class source)"],
     "basis": "internet reach exists: the tier's knowledge is not bounded by its local weights — this is why low is a tier, not a handicap"},
]

def main():
    out_dir = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "."
    ctx = {"ports": listening_ports(), "relay_paths": mediamtx_paths()}
    found, missing = [], []
    feeds_present = set()
    for entry in REGISTRY:
        ok = detect(entry, ctx)
        row = {"id": entry["id"], "name": entry["name"], "kind": entry["kind"],
               "found": ok, "feeds_plugin": entry["feeds"],
               "lane": lane_for(entry, ok),
               "reference": entry.get("reference", {})}
        if entry.get("doctrine"):
            row["doctrine"] = entry["doctrine"]
        if entry.get("note"):
            row["note"] = entry["note"]
        if entry.get("degraded_rule"):
            row["degraded_rule"] = entry["degraded_rule"]
        (found if ok else missing).append(row)
        if ok:
            feeds_present.add(entry["feeds"])
    offers = [o for o in SCRIPT_TIER_OFFERS
              if all(n in feeds_present for n in o["needs"])]
    unrecognized = sorted(p for p in ctx["ports"]
                          if p not in {11434, 8090, 8091, 8092, 8971, 1883, 9997,
                                       8554, 8556, 1984})
    result = {"host": platform.node(), "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
              "relay_paths_local": ctx["relay_paths"],
              "pipes_found": found, "pipes_not_found": [m["id"] for m in missing],
              "reference_instances": REFERENCE_INSTANCES,
              "script_tier_offers": offers,
              "unrecognized_listeners": unrecognized,
              "honesty": "A pipe found but not in the registry is listed, never "
                         "silently dropped; a registry pipe not found is not promised."}
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "pipes.json"), "w") as f:
        json.dump(result, f, indent=1)
    md = [f"# Recognized pipes — {result['host']} ({result['ts']})", "",
          "| Pipe | Kind | Feed → plugin | Lane |", "|---|---|---|---|"]
    for r in found:
        md.append(f"| {r['name']} | {r['kind']} | {r['feeds_plugin']} | {r['lane']} |")
    if not found:
        md.append("| (none recognized on this box) | | | |")
    md += ["", f"Not found (not promised): {', '.join(result['pipes_not_found']) or '—'}",
           f"Unrecognized listeners (listed, not dropped): "
           f"{unrecognized or 'none'}", "",
           "**Script tiers this box's feeds make possible:**"]
    for o in offers:
        md.append(f"- **{o['offer']}** — {', '.join(o['scripts'])} ({o['basis']})")
    if not offers:
        md.append("- none yet — the script floor still applies; feeds unlock offers")
    md += ["", "**Reference fleet lanes (measured on the reference install):**",
           "| Instance | Start | Lane |", "|---|---|---|"]
    for i in REFERENCE_INSTANCES:
        md.append(f"| {i['name']} | "
                  f"{('%.1fs' % i['start_s']) if i['start_s'] is not None else 'no stream'}"
                  f" | {i['lane']} |")
    with open(os.path.join(out_dir, "pipes.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md))

if __name__ == "__main__":
    main()
