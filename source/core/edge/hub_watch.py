#!/usr/bin/env python3
"""hub_watch.py — the hub's active crawl (2026-11-17, Zak's order).

The conduit's first duty is to BE the hub: it actively watches for new
additions — a USB device plugged in, new software installed, a service
like Frigate appearing — evaluates each one, and suggests how it should
integrate: what feed it joins, what lane it takes, and how the hub links
it. For services, the linking options are practical: a local web-UI link
card for the hub's service directory, and a credential POINTER (the hub
remembers where the login lives — the user's password manager / vault —
never the secret itself).

Each run: probe this node (ports, devices, units, models), diff against
the node's baseline, and emit suggestions for anything new or unlinked.
First run establishes the baseline. Read-only; suggestions are advice —
integration happens on the user's go-ahead, like everything else here.

Usage: python3 hub_watch.py [--kit DIR] [--state DIR]
Stdlib only.
"""
import glob, importlib.util, json, os, platform, socket, sys, time

# Known service signatures: how the hub recognizes a Frigate-class
# citizen and what integration it suggests. ui is a path on the node.
KNOWN_SERVICES = [
    {"match_port": 8971, "service": "Frigate NVR (authenticated UI)",
     "ui": ":8971/", "role": "archive truth + detection events",
     "feeds": "vision/archive, hearing/events", "process_hint": "frigate",
     "credential": "Frigate login — pointer: password manager entry 'Frigate'"},
    {"match_port": 5000, "service": "Frigate NVR (internal UI)",
     "ui": ":5000/", "role": "archive truth + detection events",
     "feeds": "vision/archive, hearing/events", "process_hint": "frigate",
     "credential": "usually none (internal) — verify before linking"},
    {"match_port": 8554, "service": "MediaMTX / go2rtc restream",
     "ui": ":8890/", "role": "relay — hosts camera paths for every consumer",
     "feeds": "vision/roam, vision/archive",
     "credential": "relay paths may carry per-path users — pointer: vault"},
    {"match_port": 1984, "service": "go2rtc console",
     "ui": ":1984/", "role": "stream bridging + backchannel (talkback path)",
     "feeds": "vision/local-pull, audio/backchannel",
     "credential": "usually none locally — verify before linking"},
    {"match_port": 11434, "service": "Ollama model door",
     "ui": ":11434/api/tags", "role": "conversation + deep seats",
     "feeds": "brains/conversation+deep", "credential": "none (local API)"},
    {"match_port": 1883, "service": "MQTT bus (Mosquitto)",
     "ui": None, "role": "event bus — sensors, Frigate events, stamps",
     "feeds": "events/bus", "credential": "pointer: vault entry 'mqtt' if auth is on"},
    {"match_port": 8123, "service": "Home Assistant",
     "ui": ":8123/", "role": "home state + automations peer",
     "feeds": "home/state", "credential": "pointer: password manager entry 'Home Assistant'"},
]

def load_pipes(kit):
    spec = importlib.util.spec_from_file_location("pipes", os.path.join(kit, "pipes.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def probe(kit):
    pipes = load_pipes(kit)
    ports = pipes.listening_ports()
    devices = sorted(glob.glob("/dev/video*") + glob.glob("/dev/snd/controlC*"))
    units = sorted(os.path.basename(u) for u in
                   glob.glob(os.path.expanduser("~/.config/systemd/user/*.service")))
    return {"ports": sorted(ports), "devices": devices, "units": units}

def listener_text():
    """Process names behind the listeners, for identity confirmation:
    a port alone is a hint, not a name (a bare :5000 match once claimed
    Frigate on a box that runs none)."""
    import subprocess
    out = []
    for cmd in (["ss", "-tlnp"], ["docker", "ps", "--format", "{{.Names}} {{.Ports}}"]):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            if r.returncode == 0:
                out.append(r.stdout.lower())
        except Exception:
            pass
    return "\n".join(out)

def host_hint():
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return platform.node()

def main():
    kit = sys.argv[sys.argv.index("--kit") + 1] if "--kit" in sys.argv else \
        os.path.dirname(os.path.abspath(__file__))
    state_dir = sys.argv[sys.argv.index("--state") + 1] if "--state" in sys.argv else \
        os.path.join(os.path.expanduser("~"), "ai-core-edge", "state")
    os.makedirs(state_dir, exist_ok=True)
    base_path = os.path.join(state_dir, "baseline.json")
    out_path = os.path.join(state_dir, "hub_watch.json")
    now = probe(kit)
    baseline = json.load(open(base_path)) if os.path.exists(base_path) else None
    suggestions = []
    host = host_hint()
    listeners = listener_text()
    known_ports = {s["match_port"] for s in KNOWN_SERVICES}
    for svc in KNOWN_SERVICES:
        if svc["match_port"] in now["ports"]:
            hint = svc.get("process_hint")
            confirmed = not hint or hint in listeners
            suggestions.append({
                "kind": "service", "service": svc["service"],
                "node": platform.node(),
                "status": "present — review + link" if confirmed else
                          "candidate — port matches, identity unconfirmed",
                "role": svc["role"], "feeds": svc["feeds"],
                "linking_options": (
                    [{"option": "web UI link card",
                      "target": f"http://{host}{svc['ui']}"}] if svc["ui"] else []) + [
                    {"option": "credential pointer", "target": svc["credential"]},
                    {"option": "feed hookup", "target": svc["feeds"]}],
            })
    if baseline:
        for p in sorted(set(now["ports"]) - set(baseline["ports"]) - known_ports):
            suggestions.append({
                "kind": "unknown-service", "service": f"new listener on port {p}",
                "node": platform.node(), "status": "new since last crawl — evaluate",
                "role": "unassigned", "feeds": "to be proposed after identification",
                "linking_options": [{"option": "identify, then propose",
                                     "target": f"probe http://{host}:{p}/ and process owner"}]})
        for d in sorted(set(now["devices"]) - set(baseline["devices"])):
            suggestions.append({
                "kind": "usb-device", "service": f"new device {d}",
                "node": platform.node(), "status": "new since last crawl — evaluate",
                "role": "candidate pipe (camera/mic class by device node)",
                "feeds": "vision or hearing, by device class",
                "linking_options": [{"option": "register as pipe",
                                     "target": "add to the pipe registry with a measured lane"}]})
        for u in sorted(set(now["units"]) - set(baseline["units"])):
            suggestions.append({
                "kind": "software", "service": f"new service unit {u}",
                "node": platform.node(), "status": "new since last crawl — evaluate",
                "role": "watched process candidate",
                "feeds": "the hub directory (watched processes)",
                "linking_options": [{"option": "add to directory",
                                     "target": "name, location, exec — watched by the hub"}]})
    json.dump(now, open(base_path, "w"), indent=1)
    report = {"node": platform.node(), "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
              "baseline_was": "established this run" if baseline is None else "diffed",
              "suggestions": suggestions}
    json.dump(report, open(out_path, "w"), indent=1)
    print(f"hub watch on {report['node']}: {len(suggestions)} suggestion(s) "
          f"({report['baseline_was']}) -> {out_path}")
    for s in suggestions:
        print(f"  - [{s['kind']}] {s['service']}: {s['status']}")

if __name__ == "__main__":
    main()
