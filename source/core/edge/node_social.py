#!/usr/bin/env python3
"""node_social.py — the hourly dwell social, as a readable digest (2026-11-17).

Zak's design: the nodes chat in dwell social, hourly, for five minutes —
about system, connections, stability, and progress, for the user and for
their individual goals. This generator produces that five-minute read
from the node reports + conduit advisories: deterministic in v0 (the
receipts speak first); a model-voiced version fills the same sections
later and may not invent numbers the reports don't carry.

Usage: python3 node_social.py --nodes DIR [--out SOCIAL.md]
"""
import json, os, sys, time

def main():
    nodes_dir = sys.argv[sys.argv.index("--nodes") + 1]
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else \
        os.path.join(nodes_dir, "SOCIAL.md")
    tabs = json.load(open(os.path.join(nodes_dir, "tabs.json")))
    advisories = json.load(open(os.path.join(nodes_dir, "advisories.json")))
    lines = [f"# Node social — {time.strftime('%Y-%m-%d %H:%M %Z')}", "",
             "Five minutes, four subjects: system, connections, stability, progress.", ""]
    for name, t in tabs["tabs"].items():
        h = t["headroom"]
        age_txt = "" if t["report_age_s"] is None else f" ({t['report_age_s']}s old)"
        lines += [f"## {name} ({t['node']}, {t['arch']}) — {', '.join(t['roles'])}",
                  f"- System: load {h['load1']} ({h['load_per_thread']}/thread), "
                  f"RAM available {h['ram_available_mb']} MB, disk free {h['disk_free_gb']} GB.",
                  f"- Connections: {len(t['pipes'])} pipes recognized "
                  f"({', '.join(p['id'] for p in t['pipes']) or 'none'}).",
                  f"- Stability: report {t['health']}{age_txt}; "
                  f"budget {t['budget']['max_parallel_model_tasks']} model task(s).",
                  f"- Progress: offers {', '.join(t['offers']) or 'the script floor'}.",
                  ""]
    u = tabs["united"]
    lines += ["## United (all nodes as one system)",
              f"- Total model seats: {u['total_model_seats']}.",
              f"- Single points of capability: "
              f"{u['single_points_of_capability'] or 'none — every tier has a second home'}.",
              f"- Hardware limit: {u['hardware_limit']}", ""]
    if advisories:
        lines.append("## Conduit advice")
        for a in advisories:
            lines.append(f"- To {a['to']}: {a['text']}")
    else:
        lines.append("## Conduit advice\n- None this hour — the system is balanced as reported.")
    text = "\n".join(lines) + "\n"
    with open(out, "w") as f:
        f.write(text)
    print(text)

if __name__ == "__main__":
    main()
