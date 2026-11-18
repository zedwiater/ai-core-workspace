#!/usr/bin/env python3
"""conduit.py — the main conduit's view of its bifurcated self (2026-11-17).

Reads every edge report in a nodes directory and produces:
  tabs.json       — the app-UI tab model: one tab per node (its tiers,
                    pipes, budget, health) + a UNITED tab (the wonder-
                    twin view: system totals, best node per tier).
  advisories.json — conduit -> node advice, the return leg of the snap
                    pipe. Rule-based and receipt-tied: every advisory
                    names the report field it comes from.
  placement       — where a task should run, and the hardware limit:
                    which demands exceed any single node (cooperation
                    required), and which exceed the whole system
                    (degrade, stated — never silently promised).

Usage: python3 conduit.py --nodes DIR [--out DIR]
Stdlib only.
"""
import json, os, sys, time

STALE_S = 3900  # hourly social cadence + margin

def load_reports(nodes_dir):
    reports = {}
    for name in sorted(os.listdir(nodes_dir)):
        p = os.path.join(nodes_dir, name, "report.json")
        if os.path.exists(p):
            reports[name] = json.load(open(p))
    return reports

def age_s(ts):
    """Timezone-aware: nodes report in their own local offset (the Pi
    fleet runs odd timezones); mktime would misread a sibling's clock
    as staleness."""
    from datetime import datetime
    try:
        return time.time() - datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z").timestamp()
    except Exception:
        return None

def main():
    nodes_dir = sys.argv[sys.argv.index("--nodes") + 1]
    out_dir = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else nodes_dir
    reports = load_reports(nodes_dir)
    tabs, advisories, united = {}, [], {}
    total_seats = 0
    tier_holders = {}
    for name, r in reports.items():
        age = age_s(r["ts"])
        health = "fresh" if age is not None and age < STALE_S else "STALE"
        seats = r["budget"]["max_parallel_model_tasks"]
        total_seats += seats
        for tier, status in r["tiers"].items():
            if "unavailable" not in status and "offline" not in status:
                tier_holders.setdefault(tier, []).append(name)
        tabs[name] = {"node": r["node"], "arch": r["arch"], "roles": r["roles"],
                      "health": health, "report_age_s": None if age is None else int(age),
                      "budget": r["budget"], "tiers": r["tiers"],
                      "pipes": r["pipes_found"], "offers": r["script_tier_offers"],
                      "headroom": r["headroom"]}
        if health == "STALE":
            advisories.append({"to": name, "kind": "check-in",
                               "text": "Report is stale — node should re-run its census and re-report.",
                               "from_field": "ts"})
        if seats == 0 and r["tiers"].get("knowledge (web)", "").startswith("available"):
            advisories.append({"to": name, "kind": "routing",
                               "text": "No local model seats: knowledge rides the web leg; conversation should be placed on a sibling with a free seat.",
                               "from_field": "budget.max_parallel_model_tasks"})
        if r["headroom"]["load_per_thread"] > 0.75:
            advisories.append({"to": name, "kind": "balance",
                               "text": "Load per thread is high — shed on-demand seats to a sibling before accepting new tasks.",
                               "from_field": "headroom.load_per_thread"})
    single_points = {t: ns for t, ns in tier_holders.items() if len(ns) == 1}
    united = {"total_model_seats": total_seats,
              "tier_holders": tier_holders,
              "single_points_of_capability": single_points,
              "hardware_limit": (
                  "A task needing more parallel model seats than the largest "
                  "single node holds requires cooperative placement across "
                  "nodes; a task needing more than the system total must "
                  "degrade along its ladder and say so.")}
    placement = {
        "conversation": "the node whose conversation tier is resident and pinned",
        "deep_batch": max(reports, key=lambda n: reports[n]["budget"]["max_parallel_model_tasks"]) if reports else None,
        "web_lookup": "any node with knowledge (web) available — cheapest first",
        "sensing": "the node holding the pipe (feeds are placed, not moved)",
    }
    os.makedirs(out_dir, exist_ok=True)
    json.dump({"tabs": tabs, "united": united, "placement": placement},
              open(os.path.join(out_dir, "tabs.json"), "w"), indent=1)
    json.dump(advisories, open(os.path.join(out_dir, "advisories.json"), "w"), indent=1)
    print(f"nodes: {list(reports)} | total model seats: {total_seats} | "
          f"single points: {single_points} | advisories: {len(advisories)}")
    for a in advisories:
        print(f"  -> {a['to']}: {a['text']}")

if __name__ == "__main__":
    main()
