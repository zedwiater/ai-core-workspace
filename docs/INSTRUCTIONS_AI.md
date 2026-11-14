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
# choices: mode home|system, brain ollama|llamacpp|none,
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
