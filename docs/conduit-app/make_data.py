#!/usr/bin/env python3
"""Bake the conduit's live state into data.js for the app UI."""
import glob, json, os

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(BASE, "..")

def load(p):
    with open(os.path.join(ROOT, p)) as f:
        return json.load(f)

hub = load("conduit/state/hub.json")
tabs = load("nodes/tabs.json")
advisories = load("nodes/advisories.json")
reports = {}
for n in ("pc", "pi5", "vm"):
    reports[n] = load(f"nodes/{n}/report.json")
watch = {}
for n in ("pc", "pi5", "vm"):
    p = os.path.join(ROOT, "nodes", n, "hub_watch.json")
    if os.path.exists(p):
        watch[n] = json.load(open(p))
social = open(os.path.join(ROOT, "nodes", "SOCIAL.md")).read()
logs = {}
for p in sorted(glob.glob(os.path.join(ROOT, "conduit", "logs", "*.log"))):
    logs[os.path.basename(p)[:-4]] = open(p).read()

data = {"hub": hub, "tabs": tabs, "advisories": advisories, "watch": watch,
        "reports": reports, "social": social, "logs": logs,
        "measured": {
            "mid_pc": "Conversation (george-14): 7.7 tok/s, load 0.0s — pinned, split GPU+CPU seat. Chat door 7B: 6.0 tok/s under full load. VL seat: 24-34s per clip review, capped. Image: 63s per 512x512 picture, heartbeat-supervised.",
            "low_vm": "Conversation (Qwen2.5-1.5B): cold load 6.6s, first token 1.0s, 8.3 tok/s solo; under contention 5.7 tok/s with first token unmoved; 3B seat announced at 30.6s under saturation, then 5.6 tok/s; ETA predicted 14.6s, measured 14.6s.",
            "floor": "No models at all: the table promises the script floor + web knowledge only — and keeps the promise.",
        }}
with open(os.path.join(BASE, "data.js"), "w") as f:
    f.write("window.CONDUIT = " + json.dumps(data) + ";\n")
print("data.js baked:", len(json.dumps(data)), "bytes")
