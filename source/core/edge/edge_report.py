#!/usr/bin/env python3
"""edge_report.py — the edge node's half of the bifurcation (2026-11-17).

Same DNA as the conduit: this kit (census.py + pipes.py + websearch.py +
edge_report.py) is what the main app clones onto an edge node. The node
runs its own census and pipe recognition, then emits ONE report — the
snap report pipe — that flows to the conduit. The conduit's advisories
flow back the same path (advisories.json, read at dwell/social time).

A node never grades itself by another node's ruler: its expectation
table is computed from ITS hardware, its pipes, its headroom.

Usage: python3 edge_report.py [--kit DIR] [--out report.json]
Stdlib only, read-only.
"""
import importlib.util, json, os, platform, subprocess, sys, tempfile, time

def run_kit_module(kit, name, out_dir):
    path = os.path.join(kit, name)
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    mod = importlib.util.module_from_spec(spec)
    argv = sys.argv
    sys.argv = [name, "--out", out_dir]
    try:
        spec.loader.exec_module(mod)
        mod.main()
    finally:
        sys.argv = argv

def local_processes():
    """Watched processes with locations, from this node's own service
    wiring — the conduit's directory of what runs where."""
    import glob as _glob, re as _re
    procs = []
    for unit in sorted(_glob.glob(os.path.expanduser("~/.config/systemd/user/*.service"))):
        try:
            text = open(unit).read()
        except Exception:
            continue
        m = _re.search(r"ExecStart=(\S+)", text)
        procs.append({"name": os.path.basename(unit), "location": unit,
                      "exec": m.group(1) if m else None})
    return procs

def main():
    kit = sys.argv[sys.argv.index("--kit") + 1] if "--kit" in sys.argv else \
        os.path.dirname(os.path.abspath(__file__))
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "report.json"
    with tempfile.TemporaryDirectory() as td:
        run_kit_module(kit, "census.py", td)
        run_kit_module(kit, "pipes.py", td)
        census = json.load(open(os.path.join(td, "expectations.json")))
        pipes = json.load(open(os.path.join(td, "pipes.json")))
    budget = census["expectations"]["budget"]
    tiers = {t["tier"]: t["status"] for t in census["expectations"]["tiers"]}
    found = pipes["pipes_found"]
    roles = []
    if any(p["id"].startswith("rtsp") or p["id"] == "frigate-nvr" for p in found):
        roles.append("sensing/archive")
    if pipes.get("relay_paths_local"):
        roles.append("relay")
    if budget["max_parallel_model_tasks"] >= 1:
        roles.append("compute")
    if any(p["kind"] == "audio" for p in found):
        roles.append("hearing")
    if not roles:
        roles.append("observer (script floor + reporting)")
    report = {
        "node": platform.node(), "arch": platform.machine(),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "dna": "ai-core edge kit v0 (census + pipes + websearch)",
        "roles": roles,
        "cpu": census["cpu"], "ram_mb": census["ram"]["effective_mb"],
        "budget": budget, "tiers": tiers,
        "pipes_found": [{"id": p["id"], "feeds": p["feeds_plugin"], "lane": p["lane"]}
                        for p in found],
        "pipes_not_found": pipes["pipes_not_found"],
        "script_tier_offers": [o["offer"] for o in pipes["script_tier_offers"]],
        "headroom": {
            "load1": census["cpu"]["load1"],
            "load_per_thread": census["cpu"]["load_per_effective_thread"],
            "ram_available_mb": census["ram"]["available_mb"],
            "disk_free_gb": census["disk_free_gb"],
        },
        "watched_processes": local_processes(),
    }
    with open(out, "w") as f:
        json.dump(report, f, indent=1)
    print(f"node {report['node']} ({report['arch']}) roles={roles} "
          f"budget={budget['max_parallel_model_tasks']} model tasks, "
          f"{len(found)} pipes -> {out}")

if __name__ == "__main__":
    main()
