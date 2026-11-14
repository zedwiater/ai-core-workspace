# AI Core — Instructions (AI-executable spec)

**The system is just a set of permission gradients leading to full autonomy.**

Status: DRAFT. Audience: an AI agent executing setup, extension, or
maintenance on an owner's machine. Every rule below is normative.
Where this spec and the code disagree, the code is the bug — file a
census proposal; do not improvise.

## 0. Layout

Repo layout (development):

```
README.md
install.sh
source/
  app/ai-client.py        # GTK client (the doors)
  config.json             # offered values: model, max_loops,
                          # timeout, mcp_ports, theme, sandbox, backup
  core/
    protocol.py           # wire contract + SERVICE_PORTS (routes)
    ring_service.py       # scaffold + label machinery
    loop.py               # Intercept & Compute tool loop
    floor.py              # base floor: wake + dwell alignment
    intake.py             # Joy Calculator intake
    settings.py           # Options store (memory key app:options)
    models.py             # model stacks (memory key app:model-stacks)
    learn.py              # explainers + Learn sections, 3 layers
    toy.py                # Eddy Toy physics (pure)
    setup.py              # plan-first bootstrap engine (pure plans)
    selfmaint.py          # census / safe fills / proposals
    hybrid.py             # parent/daughter briefs + receipt chain
  rings/{actuation,atmosphere,state}/mcp-*.py   # the 8 services
tests/                    # unittest suite (stdlib only)
selfmaint/                # census receipts, backups, proposals
```

Installed layout: the same tree rooted at `/opt/ai-core` (system)
or `~/ai-core` (home minimum), with `core.tree_layout`-equivalent
resolution: if `<root>/source` exists it is the source root, else
`<root>` is.

Wire contract (unchanged, invariant): one JSON object per TCP
connection to `127.0.0.1:<port>`, one JSON reply, connection
closed. Request: `{"action": <name>, ...}`. Ports:
files 9101, web 9102, vision 9103, shell 9104, sound 9105,
voice 9106, coding 9107, memory 9108 (`core.protocol.SERVICE_PORTS`
is the single source of truth).

## 1. Install (plan-first)

Use `core.setup`:

```python
profile = setup.detect_profile()          # READ-ONLY probes only
plan    = setup.build_plan(profile, choices, src_dir=<tree root>)
# choices: mode home|system, brain ollama|llamacpp|wici|none,
#          network local|lan|tailnet, api_tiers bool,
#          chat_doors bool, pair bool,
#          role parent|daughter|hybrid
runnable, held = setup.steps_for_level(plan, level)
script  = setup.render_script(plan, level)  # dry run, first-class
```

Rules:

- `build_plan` and `render_script` are pure. Never execute a step
  except through the UI action, one step at a time, in plan order.
- Privilege levels: 0 = look only; 1 = user-space only; 2 = ask
  per sudo step with the exact command displayed before it runs;
  3 = standing grant for this setup session only. Default: the
  lowest level that completes the chosen plan. **No silent sudo,
  ever.** A step whose `min_level` exceeds the granted level is
  HELD — announced, listed, never dropped silently.
- The plan's `totals` (disk_gb, download_gb, minutes,
  network_steps, money) and `footprint` MUST be presented before
  any step runs. Money is "$0 by default".
- Model sizing comes from `setup.recommend_models(profile)`
  (cores + RAM + VRAM basis). `plan["minimums"]` is the floor row
  (measured precedent: 1.5B-class chat on full CPU, i3 Chromebook,
  repo screenshot `glazing_chromebook_success.png`). Estimates are
  labeled estimates; measured tok/s replaces them post-install.
- Package branches by `profile["pkg_mgr"]`: apt | dnf | pacman.
  Arch: pacman branch; the app never modifies kernel, bootloader,
  or initramfs (mkinitcpio is out of scope for the app).
- `brain="wici"` is the WiCi split brain (InferSSD-style):
  `recommend_models(profile, brain="wici")` re-sizes the REASON
  slot only, against the combined VRAM + usable-RAM pool, and
  `build_plan` adds `plan["wici"]` — the fulcrum split
  (β\* = Rc/(Rc+Rg) under an ASSUMED rate model, constants in
  `core.setup`), per-slot `legs` (chat → GPU unsplit; reason →
  GPU+CPU seesaw; summarizer → CPU, so no leg idles), the SSD
  `feed` bound, and a `patience_cost` latency figure, all
  mirrored into `limits["declared"]`. Leadership follows the
  rate model, never a fixed GPU-first rule: when the CPU leg's
  rate exceeds the GPU leg's, β\* > 0.5 and the CPU leads the
  experts — free-range inversion. The engine step is
  guided-manual (InferSSD is CUDA-only; no URL is named). On
  any non-Nvidia profile the plan is FAUX: split, legs, feed
  bound and patience cost are computed and printed, but no
  engine or model step is emitted — the plan is the split it
  WOULD use, labeled as such in `plan["wici"]["faux"]`, the
  declared limits, and the dry-run rendering.
- Secrets: `setup.save_secret(name, value)` →
  `~/.config/ai-core/secrets.json`, mode 0600, values never
  logged, never required. `setup.load_secret(name)` reads them.

## 2. Add a service (script plug) — label + route, nothing else

Label block (module docstring OR leading comments; parsed by
`core.ring_service.parse_label`):

```
Label-Name: <service name, must equal the serve() name>
Label-Origin: <who/what shipped this script>
Label-Version: <version string>
Label-Hash: <optional: content hash or provenance note>
Label-Does: <one line: what it does>
```

Complete = name, origin, version, does all present
(`ring_service.label_complete`).

Route: the script must call
`serve("<name>", "<ring>", <port>, {<action>: <handler>, ...})`
(from `core.ring_service`), and `<port>` MUST equal
`SERVICE_PORTS[<name>]` (verified by
`ring_service.serve_route`).

Semantics:

- Labeled + routed → the service is picked up by the floor's
  probes and the census automatically on the next wake/dwell beat.
- Unlabeled → census finding `gap-label-<name>`, class SAFE:
  `selfmaint.apply_safe_fills` backfills a label derived from the
  route, with backup + receipt. Idempotent.
- Unrouted / port-drifted / unregistered name → census finding
  `gloss-route-<name>-*`, class PROPOSAL. Joining the registry is
  the owner's decision. **Never enable an unrouted script
  silently.**
- Expansion and self-maintenance execute through the existing
  organs only (memory service for receipts, files on the state
  ring for backups/proposals). There is no separate expansion
  engine; do not build one.

## 3. Models

`core.models`: slots `chat | reason | summarizer`; stacks persist
at memory key `app:model-stacks`. Entry shapes:

```json
{"kind": "ollama", "model": "<name>"}
{"kind": "openai", "base_url": "<https://…/v1>", "model": "<name>",
 "api_key": "<optional>"}
```

Chat serving: `models.resolve_chat_entry(stacks, policy,
budget_ok)` returns the first reachable, policy-allowed entry +
a per-entry verdict report. Policies (Options → cloud): `never`
(local only), `draft` (cloud answers are prefixed as drafts),
`allowed` (inside the session budget). A swap is never silent:
the verdict report and the serving label state who served.
Ring scaling on poor hardware: summarizer (tiny) takes breadth,
chat (small) takes basic use, reasoner spends only on dwell/deep
asks.

## 4. Pairing

Daughter pairing:

1. Parent side: `setup.generate_pairing_secret()` → show ONCE →
   `setup.save_secret("pairing-secret", s)`.
2. Daughter side: role `daughter` (Options key `app:options`,
   group `hybrid`), `parent_host`, `parent_port` (default 9108),
   same secret saved the same way.
3. Transport: on each floor beat, `hybrid.DaughterRuntime.beat`
   builds a brief via `hybrid.build_brief` (floor summary only —
   **no raw audio/video, ever**), appends it to the hash-linked
   chain (`hybrid.ChainStore`, sha256 over prev-hash + canonical
   JSON), and sends `{"action": "set", "key":
   "daughter:<id>:brief", "value": <entry json>}` to the parent's
   memory service. Failure → `hybrid.BriefQueue` (JSONL outbox),
   drained in order on later beats.
4. Parent verification: `hybrid.read_daughters` reports per
   daughter: age, stale (vs `hybrid.stale_minutes`), `verified`
   (pair-secret match), `chain_ok` (entry hash re-verifies).

SSH pairing: `setup.pairer_script(pubkey_line, label)` returns an
exportable `.sh`; it validates the key, prints its OpenSSH SHA256
fingerprint (`setup.key_fingerprint`) before the user-pressed
install, and writes the key into `authorized_keys` prefixed with
`from="100.64.0.0/10"`. Idempotent. Pairing is always a
user-pressed action with the fingerprint displayed. Never
generate trust silently.

## 5. Approvals — the two limits

Every approval surface MUST show both:

- **declared**: `plan["limits"]["declared"]` — models chosen,
  mode, network bind, privilege ceiling;
- **actual**: `plan["limits"]["actual"]` — measured cores, RAM,
  VRAM, usable GB + basis, free disk.

Rule (verbatim intent): to push past a declared limit, provide
power and data — a bigger local model, more hardware headroom, an
API tier, more storage. The app never just raises a number.
`selfmaint.census(root, profile=...)` files
`gloss-limits-declared-vs-actual` (proposal class) when config's
declared model exceeds the profile's usable memory.

## 6. Self-maintenance

`core.selfmaint.SelfMaintainer(root, state_dir).run_beat(beat,
profile=None)` — invoked ONLY as the floor's companion on wake
and dwell beats; never mid-conversation.

- Census classes: SAFE fills (mechanical only: advertisement
  alignment through `ACTION_ALIASES` — reality wins; label
  backfill; generated explainers labeled as generated) vs
  PROPOSALS (everything behavioral). Fills: backup first
  (`<state_dir>/backups/<file>.bak-<ts>`), receipt recorded,
  idempotent. Proposals: one `.md` per finding id under
  `<state_dir>/proposals/`, deduped by id, never auto-applied.
- Census persists to memory key `selfmaint:<session>:census`.
- Gloss (owner's definition): a detail that doesn't align with
  the rounded plan.

## 7. Hard limits for the executing agent

- Do not execute setup steps on a machine while merely
  inspecting, documenting, or testing this build. Execution is a
  UI action on the target box.
- Do not bypass the privilege gradient, the pairing button, or
  the census classes to "save time".
- Do not delete the only copy of anything. Fills keep backups;
  proposals keep the original.
- GTK runtime requires PyGObject + a display; headless
  verification is: `python3 -m unittest discover -s tests -t .`
  plus `python3 -m compileall source/`.

## 8. Observer mode (headless)

The rings run without the client:

- Launch the 8 services (`rings/{actuation,atmosphere,state}`)
  as plain detached processes (e.g. `setsid`), loopback only —
  the wire contract already binds `127.0.0.1`. The GTK client
  is NOT started; PyGObject and a display are not required in
  this mode. No client doors are available headless.
- Alongside them, run a snapshot loop: every 60 s append one
  JSON line to `snapshots.jsonl`: `{ts, loadavg, mem totals,
  proc_count, services: {<name>: "ok"|"down"}, service_pids,
  services_rss}`. The snapshot file is the observer's flowing
  floor of its host and the evidence base for host-state
  questions — an additional discussion angle, not a guess.
- Observer folder (pattern, not a fixed path): start/stop
  scripts, `logs/`, `pids/`, `snapshots.jsonl`. Start MUST be
  idempotent: pidfiles hold the real service PIDs, never
  wrapper shells; a re-run reports already-running services
  instead of duplicating them. Stop MUST verify each PID's
  command line matches the expected service before signaling
  (PID-reuse guard), snapshot loop first, TERM→KILL grace.
- "Up" is evidence-only: real pings through
  `core.protocol.call_service` (expect `pong` from all 8) PLUS
  snapshot lines present on disk. A launch message is not
  evidence. Measured footprint (real VM run): services ≈103 MB
  RSS total (12–17 MB each), snapshot loop ≈12 MB.
- Limits, to be stated wherever this mode is described: the
  services are plain processes, NOT systemd units. A host
  restart kills them; the mode does not self-recover. Recovery
  is re-running the start script.

## 9. Joy Calculator personal profile (owner-granted)

Under an explicit grant from the owner, the `core.intake`
intake (13 agree/disagree statements) MAY be answered from the
owner's own data and conversation history, producing a personal
profile the app can answer questions from. Rules are normative:

- Every answered statement carries: the verbatim statement, the
  answer, a source citation into the owner's record, and a
  confidence mark — `Direct` (the owner stated or contracted
  it) or `Practice` (the owner's standing documented operating
  pattern).
- A statement the record does not settle MUST be recorded
  UNANSWERED. Never infer a position in the owner's name;
  never fill a gap to complete the set.
- Deliverables: a statement-by-statement profile and a Q&A
  sheet, and they MUST include an explicit cannot-answer list —
  the questions the underlying data does not support.
- Privacy spine: the profile and Q&A are the owner's data.
  They stay local, outside the shipped tree; only the method
  is documented and shippable. Structure ships; house data
  never ships. Never commit a personal profile to this
  repository.

## 10. Gradient-governed latitude

Latitude for autonomous work (observer operation, profile
building, census beats) is governed by three gradients; take
the most latitude the three jointly allow:

- **Confidence**: scale with measured agreement — verified
  pings, landed snapshots, agreeing checks. Disagreement
  contracts latitude immediately.
- **Comfort**: privilege advances only in announced steps on
  the §1 gradient; the owner's tap is the gate. Never take a
  step that was not offered.
- **Patience**: let baselines and profiles form at their
  natural cadence (floor windows, dwell beats). Do not force,
  backfill, or fake maturity to reach a state sooner.
