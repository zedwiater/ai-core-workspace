# Installing the conduit refinement (walked 2026-11-17)

These steps were executed end-to-end from a clean directory using only
the files in this repository, on a bare 4-core VM with no models
installed. Every command below ran and produced the stated result.
The v1 desktop app keeps its own installer (`install.sh`, README);
this document covers the refinement modules only. They are stdlib-only
Python 3 — no pip installs, no sudo.

## 1. Assemble the edge kit (flat directory)

The kit is six files in ONE directory — on a conduit, on an edge node,
the layout is the same:

```sh
mkdir -p ~/ai-core-kit
cp source/core/census.py source/core/pipes.py source/core/websearch.py ~/ai-core-kit/
cp source/core/edge/edge_report.py source/core/edge/hub_watch.py source/core/edge/disconnect.py ~/ai-core-kit/
```

## 2. Crawl the box (read-only)

```sh
cd ~/ai-core-kit
python3 census.py --out .   # writes expectations.json + expectations.md (the tier table)
python3 pipes.py --out .    # writes pipes.json + pipes.md (recognized pipes + lanes)
```

## 3. File the node's report (edge nodes) or read the table (standalone)

```sh
python3 edge_report.py --out report.json
# prints: node <host> (<arch>) roles=[...] budget=N model tasks, M pipes
```

On an edge node, `report.json` is the snap report that flows to the
conduit. On the conduit, collect reports under `nodes/<name>/` and run
`source/core/edge/conduit.py --nodes nodes --out nodes`, then
`node_social.py` for the hourly digest.

## 4. The disconnect cycle (conduit)

```sh
python3 disconnect.py snapshot --home ~/conduit-home   # arrangement as found
python3 disconnect.py adopt    --home ~/conduit-home   # hub registry built
python3 disconnect.py status   --home ~/conduit-home   # ADOPTED, pipe/seat counts
python3 disconnect.py release  --home ~/conduit-home   # bilateral return, hub archived
```

Adoption is registry-level: processes keep flowing; the conduit hosts
the map, metrics, routing and tier-categorized logs.

## 5. Hub watch (active monitoring, optional per node)

```sh
python3 hub_watch.py --state ~/ai-core-kit/state   # first run sets the baseline
```

For hourly runs, install a user timer (units verified on the reference
fleet): a oneshot `hub-watch.service` running
`/usr/bin/python3 %h/ai-core-edge/hub_watch.py` (adjust the path) plus
a `hub-watch.timer` with `OnCalendar=hourly`, `Persistent=true`.

## What "working" looked like in the walk

census and pipes printed their tables; edge_report filed a report
(budget 0 on the bare VM — its Ollama was down, and the table said so
instead of inventing a seat); hub_watch established its baseline with
0 suggestions; the disconnect completed snapshot -> adopt -> release
with per-tier log lines. On a stocked machine the same steps yield the
full tables in docs/BENCH-20261117.md.

## What the desktop client shows on first launch (2026-11-17)

The v1 client's installer (install.sh) now runs this crawl as its
Step 4.5 and narrates it — hardware, budget, tier promises, pipe
findings, and advice (CPU-seat expectations, model pull state, the
web-knowledge note) — and its final banner states the model-door
truth. On launch, `ai-client` opens on the **Conduit landing**
(simple view first; Advanced unfolds the full tables), with Joy
Gradient, Nodes, Dwell, Roam Watch and Help & Support tabs beside
the chat. The landing is the crawl, rendered by
source/app/conduit_pages.py from the same core modules.

## Installer merge semantics (2026-11-17, Zak's order)

The installer merges with a tuned system instead of overwriting it:
an owner Ollama drop-in means merge mode (nothing written, nothing
restarted, nothing pulled); otherwise the app writes only its own
ai-core.conf drop-in. Existing models are never pulled over — the
shelf decides the app's factory default, and the keep/upgrade advice
is a first-launch popup (conduit_pages.model_advice).
The landing also carries plain-language switches for the script
behaviors (model-advice popup, clickable service doors,
new-arrival suggestions) — each persists to
~/.config/ai-core/conduit.json and is read by the behavior it names.
