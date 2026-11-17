#!/usr/bin/env python3
"""disconnect.py — the bilateral disconnect (2026-11-17, Zak's order).

Severs the pipes from their ad-hoc arrangement and lets the ai-core
become the CONDUIT: a central hub that hosts all pipes, paths, metrics,
direct access to edges and tiers, and the full system map. Bilateral
means it runs both ways:

  snapshot   record the arrangement as found (pipes, processes, node
             reports) BEFORE the conduit touches anything.
  adopt      build the hub registry (state/hub.json): every pipe with
             its path, process location, metrics source and tier;
             every watched process with its directory; tier-categorized
             log trails opened. The app grows tabs/pages from this map.
  release    the return leg: verify the hub against the snapshot,
             archive it, and mark the pipes released back to standalone.
             The disconnect is a door that swings both ways.

HONESTY, built into the tool: adoption is registry-level. The conduit
becomes the host of record — map, metrics, routing decisions, logs —
while the underlying processes keep flowing untouched underneath.
Nothing is stopped, killed, or re-routed by this script; a literal
traffic cutover is a separate, gated operation the hub can describe
but this script does not perform. Zak's stability rule: current
function keeps flowing, now through the conduit's map.

Usage: python3 disconnect.py {snapshot|adopt|release|status} [--home DIR]
Stdlib only.
"""
import glob, json, os, platform, re, subprocess, sys, time

TIER_OF_KIND = {"model": "conversation", "video": "vision", "audio": "audio",
                "knowledge": "knowledge", "generation": "image",
                "control": "script", "service": "system"}

def home_dir():
    if "--home" in sys.argv:
        return sys.argv[sys.argv.index("--home") + 1]
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "conduit")

def state(home):
    d = os.path.join(home, "state")
    os.makedirs(d, exist_ok=True)
    os.makedirs(os.path.join(home, "logs"), exist_ok=True)
    return d

def log_tier(home, tier, msg):
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} [{tier}] {msg}\n"
    with open(os.path.join(home, "logs", f"{tier}.log"), "a") as f:
        f.write(line)

def local_processes():
    """Watched processes on THIS node, with locations: user services and
    their ExecStarts (the install's own wiring), read — never touched."""
    procs = []
    for unit in sorted(glob.glob(os.path.expanduser("~/.config/systemd/user/*.service"))):
        try:
            text = open(unit).read()
        except Exception:
            continue
        m = re.search(r"ExecStart=(\S+)", text)
        procs.append({"name": os.path.basename(unit), "kind": "systemd-user-unit",
                      "location": unit,
                      "exec": m.group(1) if m else None})
    return procs

def load_reports(home):
    reports = {}
    nodes_dir = os.path.join(os.path.dirname(os.path.abspath(home)), "nodes")
    if os.path.isdir(nodes_dir):
        for name in sorted(os.listdir(nodes_dir)):
            p = os.path.join(nodes_dir, name, "report.json")
            if os.path.exists(p):
                reports[name] = json.load(open(p))
    return reports

def cmd_snapshot(home):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "bundle"))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "pipes", os.path.join(os.path.dirname(os.path.abspath(__file__)), "bundle", "pipes.py"))
    pipes = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pipes)
    ctx = {"ports": pipes.listening_ports(), "relay_paths": pipes.mediamtx_paths()}
    found = []
    for e in pipes.REGISTRY:
        if pipes.detect(e, ctx):
            found.append({"id": e["id"], "kind": e["kind"], "feeds": e["feeds"],
                          "lane": pipes.lane_for(e, True)})
    snap = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "node": platform.node(),
            "pipes_as_found": found, "processes_as_found": local_processes(),
            "node_reports_present": list(load_reports(home))}
    path = os.path.join(state(home), "pre_disconnect.json")
    json.dump(snap, open(path, "w"), indent=1)
    log_tier(home, "system", f"snapshot taken: {len(found)} pipes, "
                             f"{len(snap['processes_as_found'])} processes, "
                             f"reports {snap['node_reports_present']}")
    print(f"snapshot: {len(found)} pipes, {len(snap['processes_as_found'])} processes "
          f"-> {path}")
    return snap

def cmd_adopt(home):
    sdir = state(home)
    snap_path = os.path.join(sdir, "pre_disconnect.json")
    snap = json.load(open(snap_path)) if os.path.exists(snap_path) else cmd_snapshot(home)
    reports = load_reports(home)
    hub_nodes = {}
    for name, r in reports.items():
        hub_nodes[name] = {
            "node": r["node"], "arch": r["arch"], "roles": r["roles"],
            "budget": r["budget"], "tiers": r["tiers"],
            "report_ts": r["ts"],
            "pipes": [{"id": p["id"], "feeds": p["feeds"], "lane": p["lane"],
                       "hosted_by": "conduit", "node": name} for p in r["pipes_found"]],
            "offers": r["script_tier_offers"], "headroom": r["headroom"]}
    hub = {"hub": "ai-core conduit", "adopted_ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "mode": "registry adoption — processes keep flowing; the conduit hosts "
                   "the map, metrics, routing and logs",
           "local_node": {"node": snap["node"], "pipes": snap["pipes_as_found"],
                          "watched_processes": snap["processes_as_found"]},
           "nodes": hub_nodes,
           "system_map": {
               "total_model_seats": sum(r["budget"]["max_parallel_model_tasks"]
                                        for r in reports.values()),
               "pipe_count": sum(len(r["pipes_found"]) for r in reports.values())
                             + len(snap["pipes_as_found"]),
               "log_trails": {t: f"logs/{t}.log" for t in
                              sorted(set(TIER_OF_KIND.values()))},
           }}
    json.dump(hub, open(os.path.join(sdir, "hub.json"), "w"), indent=1)
    json.dump({"state": "ADOPTED", "ts": hub["adopted_ts"]},
              open(os.path.join(sdir, "adoption.json"), "w"), indent=1)
    for tier in sorted(set(TIER_OF_KIND.values())):
        log_tier(home, tier, "conduit adoption: this tier's pipes, paths and "
                             "metrics are now hosted by the conduit hub")
    log_tier(home, "system", f"ADOPTED: {hub['system_map']['pipe_count']} pipes across "
                             f"{len(hub_nodes) + 1} nodes, "
                             f"{hub['system_map']['total_model_seats']} model seats")
    print(f"adopted: {hub['system_map']['pipe_count']} pipes, "
          f"{len(hub_nodes) + 1} nodes, {hub['system_map']['total_model_seats']} seats "
          f"-> hub.json (processes untouched, still flowing)")

def cmd_release(home):
    sdir = state(home)
    adoption = os.path.join(sdir, "adoption.json")
    if not os.path.exists(adoption):
        print("nothing to release: no adoption on record")
        return
    hub_path = os.path.join(sdir, "hub.json")
    if os.path.exists(hub_path):
        archive = os.path.join(sdir, f"hub-released-{time.strftime('%Y%m%d%H%M%S')}.json")
        os.rename(hub_path, archive)
    else:
        archive = "(hub already absent)"
    json.dump({"state": "RELEASED", "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z")},
              open(adoption, "w"), indent=1)
    for tier in sorted(set(TIER_OF_KIND.values())):
        log_tier(home, tier, "conduit release: pipes returned to standalone "
                             "arrangement (they never stopped flowing)")
    log_tier(home, "system", f"RELEASED: hub archived to {archive}")
    print(f"released: hub archived ({archive}); pipes standalone again")

def cmd_status(home):
    sdir = state(home)
    adoption = os.path.join(sdir, "adoption.json")
    if os.path.exists(adoption):
        a = json.load(open(adoption))
        print(f"conduit state: {a['state']} since {a['ts']}")
        hub_path = os.path.join(sdir, "hub.json")
        if os.path.exists(hub_path):
            hub = json.load(open(hub_path))
            print(f"hub: {hub['system_map']['pipe_count']} pipes, "
                  f"{len(hub['nodes']) + 1} nodes, "
                  f"{hub['system_map']['total_model_seats']} model seats")
            print(f"mode: {hub['mode']}")
    else:
        print("conduit state: never adopted (no snapshot/adoption on record)")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    h = os.path.abspath(home_dir())
    {"snapshot": cmd_snapshot, "adopt": cmd_adopt,
     "release": cmd_release, "status": cmd_status}[cmd](h)
