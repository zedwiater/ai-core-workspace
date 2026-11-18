# App Experience, Education, and the Alignment Harness

**The system is just a set of permission gradients leading to full autonomy.**

Status: DRAFT for Zak's red pen. Written 2026-11-13 from Zak's direction:
education and back story alongside technical redundancy and free-tier
optimization; plenty of option buttons; hover/pop-up explainers with a dwell
tick for backend patience and cadence scaling; pretty and informative
throughout; every function and MCP pipe should only need a plug; models
accepted from any angle; multi-model ring stacks.

## The one-sentence product

AI Core is a local-first agency app: a person chooses how deep the
relationship starts, plugs in whatever models and tools they actually have,
and the system keeps itself aligned by checking home first — wake and dwell —
before it believes its own words.

## Education is a surface, not a manual

Every screen teaches while it works. The app carries three reading layers at
once, switchable anywhere:

1. **Plain layer** — what this does, in ordinary words.
2. **Back-story layer** — where it came from: the basement lab, George, the
   Sensor Ego floors, the night the local brain could not start a thread and
   the harness held anyway. Short stories, attached to the feature they
   explain, never a separate lore dump.
3. **Technical layer** — the receipts: ports, rings, floors, gradients,
   redundancy chains, measured speeds, what is local, what is free tier, what
   costs money and why.

Education sits beside the controls it explains. A person should be able to
learn the whole system by using it, hovering, and opening explainers — no
external documentation hunt.

## Back story, told in place

- **The Joy Calculator** explains itself as it goes: it began as the question
  "how deep should this relationship start?" — answered with agree/disagree
  statements, not a settings page.
- **The base floor** carries its story: monitors used to shout constantly;
  now alignment breathes on wake and dwell only, because a system that
  checks itself without rest teaches itself anxiety.
- **Floors and gradients** carry the Sensor Ego story: a sense is not a
  number, it is a living baseline with an inverse — a flowing floor first,
  detection second.
- **Redundancy** carries the outage story: on 2026-11-13 the local stack's
  process table filled and the chat brain could not start a thread; the data
  pipes, the floors, and the receipts never stopped. The harness is designed
  so a dead brain is an event, not the end of the organism.
- **Free-tier optimization** carries the gatekeeper-bypass story: local
  first, free tiers as arbitrage, paid only when a measured wall says so —
  a kid in a basement should be able to replicate the whole thing.

## Options everywhere, all of them honest

Plenty of option buttons — and every option shows its cost before it is
chosen. Standing option groups:

- **Relationship**: theme/depth (L1–L5), prime pack, check-in cadence,
  question budget, what reaches the human and when.
- **Patience**: turn-hold, drain grace, silence window, dwell interval —
  each with the measured speed of the currently loaded model beside it, so
  patience is set against evidence, not vibes.
- **Cadence scaling**: how fast background beats run (lens ticks, dwell
  checks, digestion passes) — scaled to the machine: full cadence when the
  box is empty, polite cadence when the family is on it.
- **Models**: per-ring model stacks (below), fallback order, free-tier
  budget, when cloud is allowed to answer and when it must only draft.
- **Senses**: which organs are live, floor margins, spike thresholds, pin
  rules, retention horizons, compression tiers.
- **Redundancy**: how many independent pipes must agree before an action is
  trusted; what degrades first when the machine is starving.

Every option is a button or a small set of buttons — no config-file spelunking
required to run the system. The config file remains, for those who want it;
the app is the front door.

## Hover and pop-up explainers with a dwell tick

Explainers obey the same patience doctrine as the backend:

- A hover must **dwell** before its explainer opens (short, adjustable tick)
  — no pop-up storms from a passing cursor.
- An open explainer carries **live state**: not generic help text, but the
  current floor, the loaded model, its measured tok/s, the queue ahead of
  the request, and the patience the backend is currently asking for.
- Explainer refresh **scales its cadence** to backend health: snappy when
  the box is idle, slow and calm when the box is loaded, silent when the
  pipe is down — and it says which of those it is.
- Explainers can be pinned open as pop-ups for teaching moments (showing a
  kid, a spouse, a collaborator how a piece works) and they keep the dwell
  tick running, so the lesson updates at the system's real breathing rate.

## Pretty and informative, throughout

Beauty is a functional requirement here, in Zak's standing sense: it is how
a tired person at midnight can still read the state of the house at a glance.

- Every ring has a color, a glyph, and a one-line state.
- Gradients are drawn as gradients (floors, confidence tiers, joy), not as
  raw numbers in a grid.
- Health is transductive: the app shows what each layer reports about
  itself, in-band, in the same visual language everywhere.
- Nothing important is only in a log file. Logs are receipts; the app is
  the report.

## Plugs, not plumbing

All functions and MCP pipes should only need plugs:

- One plug contract everywhere: the existing wire shape — one JSON object
  in, one JSON object out, `ping` → `pong`, `health` → transductive report,
  actions named the same way in every ring.
- A new organ is a plug: drop a service into a ring folder, it registers,
  serves, and reports health; the floor picks it up on the next wake/dwell
  beat; the UI grows its control and explainer from its own self-report.
- A new skill is a plug: a SKILL.md pack in the skills folder; any agent
  substrate that can read it can wear it.
- A new model is a plug: any OpenAI-compatible endpoint, Ollama, a local
  router, a free-tier cloud — the ring does not care which side of the wall
  the model lives on.

## Models accepted from any angle — multi-model ring stacks

Each ring carries a **stack** of models, not a single model:

- **Chat slot**: the conversational mind (small and fast by default).
- **Reason slot**: the deep tier, slower and smarter, called on dwell and
  digestion, never blocking conversation.
- **Summarizer slot**: the inflow manager — tiny, cheap, always first to
  touch raw inflow so breadth never floods the chat slot.
- **Sense slots**: vision/sound models beside their organs in the
  atmosphere ring.
- **Fallback chain per slot**: local → second local → free tier → paid,
  ordered by the owner's ruling; a dead provider degrades to the next plug
  and the event is written down, announced on the next check-in — never a
  silent swap, never a hard failure like the 2026-11-13 thread starvation.

A model can enter from any angle: a file on disk, a router preset, a cloud
key, a neighbor machine on the LAN. The harness grades what arrives —
context size, measured speed, tool honesty — and assigns it the slot its
measurements earn.

## Redundancy and free-tier optimization (the technical spine)

- **Self-contained redundancy first**: critical paths run on the owner's
  own stack (PC / Pi / outpost). Cloud is an enhancement, never a load-
  bearing wall.
- **Control must survive the flood**: process budgets per slice so a
  runaway organ caps itself; the control pipes (shell access, gateway)
  keep reserved capacity; a spawn watchdog trips early and announces.
- **Free-tier optimization**: route by measured cost — local is free and
  first; free tiers absorb burst breadth; paid is a deliberate, logged
  decision. Token budgets are floors and gradients, not vibes: summarizer
  first, reasoner on dwell, frontier only where a gate says it earns it.
- **Graceful degradation, losses accounted**: when a tier is down the
  system steps down a named rung and says so in the check-in. Silence is
  the only unforgivable failure mode.

## Open edge (Zak, 2026-11-13)

"There is more, just can't find words." This document is deliberately
unfinished at the edges: sections land here as the words arrive, in Zak's
register first, expanded second. Nothing in this draft is frozen.

## Not busy (Zak's correction, 2026-11-13 20:17)

Yes to all of the above — but NOT busy. The surface must not become a game
menu: a wall of buttons, badges, and pop-ups shouting over each other.

- The plain surface shows state at a glance and breathes at the dwell
  cadence. Calm is the default texture.
- Options exist in depth, behind dwell and plain doors — plenty of them,
  none of them on stage unless called.
- Explainers wait to be asked (the dwell tick is also a manners tick).
- If a screen needs a manual to survive looking at it, it fails this law.

## The game (Zak's ruling, 2026-11-13 20:17)

A game CAN live in the app — as plain silly fun. Muse has to make it up.
And the game is OPEN: leave it that way.

- The game is the one un-harnessed room in the house: no grading, no
  alignment snapshots, no optimization, no joy scoring. It is not a funnel
  and it is not a lesson wearing a costume.
- It opens, you poke it, it is silly, you close it. Its state is not
  evidence about anyone.

DRAFT INVENTION (Muse's, red-pennable): **The Eddy Toy** — a quiet pond of
current on a spare tab. You poke the water and eddies spin up, drift, bump,
and sometimes merge into one big wobbling eddy that crosses the screen
wearing the disco colors the Brio never saw tonight. No score, no timer, no
losing. Sound optional and off by default. That's the whole game, on
purpose.

## v1, as built (2026-11-13)

What shipped in v1, door by door — all of it real, none of it stubbed:

- **Calm surface**: theme, one floor line, who's serving chat. Options,
  Models, Learn, Setup and the Eddy Toy live behind their own tabs.
- **Options**: grouped choices with costs — relationship themes,
  patience (dwell interval, turn timeout, explainer dwell), cadence
  scaling, senses (organs off take no new work; the floor still checks
  them), redundancy + cloud posture, self-maintenance, role &
  daughters, and a config editor that validates over the wire
  protocol before it may save.
- **Models**: per-slot stacks (chat / reason / summarizer) from Ollama
  discovery or any OpenAI-compatible endpoint. The chat path serves
  from the first reachable entry the standing cloud policy allows;
  under drafts-only, a cloud answer is labeled a draft on its face.
- **Learn**: this document's content in the app, at three reading
  layers; the same layer drives every explainer tooltip in the app.
- **The Eddy Toy**: as specced above — pure, in-memory, un-harnessed.

## First run on a fresh box (the Setup door)

The thread: **arrive → look → announce → consent gradient → thread
itself through → pair → breathe.**

1. **Look** is read-only: distro/package manager, cores, RAM, GPU,
   disk, home. No step exists before the look.
2. **Announce**: the plan states its cost up front — disk, downloads,
   time, which steps need the network, and money ($0 by default).
   The **home folder minimum** (everything under ~/ai-core, no system
   changes) is always on the table beside the system install, both
   footprints stated honestly.
3. **Consent gradient**: privilege is a gradient, never a grab —
   (0) look only, (1) user-space only, (2) ask per sudo step with the
   exact command shown first, (3) standing grant for this setup
   session only. Default is the lowest level that can do the job.
   A dry run prints the whole plan as a script; held steps print as
   comments, so reading the script tells you what a higher level
   would do. **No silent sudo anywhere.**
4. **Thread**: steps run one at a time with receipts; a failure stops
   the thread and says why, offering retry/skip/abort.
5. **Local brain, sized to the box**: models per slot are recommended
   from cores + RAM + VRAM with the reasoning shown and labeled as
   estimates. The **floor row** is measured precedent, not aspiration:
   the repo's own screenshots show this tool loop running live on an
   i3 Chromebook — a 1.5B-class model on system RAM, no GPU,
   "working slowly but working". Basic use stays fast on poor
   hardware because the internal model rings scale the answer: tiny
   summarizer first for breadth, small chat model for basic use,
   reasoner only on dwell and deep asks.
6. **Pair**: an SSH pairer script that takes a pasted public key +
   label, shows its fingerprint, and installs it restricted to the
   tailnet range (`from="100.64.0.0/10"`). Pairing is a button a
   person presses; trust is never generated silently.
7. **Breathe**: the wake/dwell floor takes over.

API tiers and chat doors (Telegram/Discord) are configuration, not
automation: keys go into a local 0600 secrets file, never logged,
never required; the signup itself is guided-manual and stays in the
owner's hands.

## The app maintains itself

Self-maintenance is on by default in the base floor — every theme —
and runs only on the wake and dwell beats, as the floor's companion.
It is a **census** of the system's declared surfaces against each
other: advertised tool actions vs implemented ones, docs vs the wire
contract, config keys vs actual reads, ring folders vs the registry,
explainer coverage, service labels and routes, and declared vs
actual limits.

- **Safe fills** are mechanical derivations from the contract itself
  — aligning an advertisement to the services' reality (reality
  wins), backfilling a service label from its route, generating a
  missing explainer. Each lands with a backup and a receipt, and is
  idempotent: a second beat finds nothing to redo.
- **Proposals** are everything beyond the mechanical — wire-shape
  changes, service renames, copy, config wiring. Filed once each as
  a patch proposal for the owner's red pen. Never auto-applied.
- A **gloss**, in Zak's sense, is a detail that doesn't align with
  the rounded plan.

First real census (2026-11-13, this tree): 16 findings — 10
advertisement misalignments repaired by safe fill (the client and
README now advertise the actions the services actually implement),
6 proposals filed (the coding `eval` response-key gloss, four
unread config keys, the web legacy-health class). Receipt:
`selfmaint/census-v1.json`; proposals: `selfmaint/proposals/`.

## Expansion: the harness grows through its own plugs

There is **no separate expansion engine**. Self-maintenance and
expansion ride the app's existing MCP + shell abilities — the census
reads the same surfaces the organs serve, receipts go to the memory
service, backups and proposals live in the state ring on disk.

A new script joins the build by exactly two steps:

1. **Source labeled** — a label block in the script (name, origin,
   version, what it does in one line; hash optional), parseable by
   `core.ring_service.parse_label`.
2. **Routed** — its `serve()` route (ring, port, actions) agrees
   with `core.protocol.SERVICE_PORTS`.

An unlabeled or unrouted script is a census finding — never silently
enabled. A labeled + routed script is picked up on the next
wake/dwell beat. All eight existing services carry labels (v1).

## Two limits at every approval

Everywhere the app asks approval — setup steps, fills, pairings —
the surface shows two limits:

- the **declared** limit: what the config/labels/plan say is being
  granted;
- the **actual built** limit: what this box measures — model sizes,
  usable memory, storage, speeds.

Rule: to push past a declared limit you **provide power and data** —
a bigger local model, more hardware headroom, an API tier, more
storage. The app never just raises a number. When declared and
actual limits drift apart unannounced, the census files a gloss.

## The George⇄daughter hybrid (v1 skeleton — honesty line)

One install, a role in config: **parent | daughter | hybrid**.

- **Daughter**: runs its atmosphere organs locally; keeps a
  hash-linked receipt chain of dwell briefs (seq, ts, prev-hash —
  the Sensor Ego pattern, minimal); on each beat emits a sized brief
  (floor state + chain head) to the parent's memory service over the
  existing wire protocol. Parent unreachable → briefs queue locally
  and drain on reconnect. **No raw audio/video ever leaves a
  daughter — descriptors and briefs only.**
- **Parent**: records daughter briefs, carries their age/staleness
  in its own floor snapshots, and lists paired daughters (last
  brief, chain head, pair verification) in Options.
- **Hybrid**: both roles on one box, briefs to its own endpoint —
  the self-test configuration, covered by the two-instance tests.

Honesty: v1 hybrid is the **briefs + chain skeleton with real
transport and real queueing — NOT the full Sensor Ego v3** (no
graded-consensus dialogue, no subconscious pass). The full stack is
the named expansion path, and it will arrive the same way everything
here arrives: labeled, routed, and censused.

## Addendum — the WiCi door (2026-11-13, evening)

Zak approved the faux-split proposal the same night it ran, with
three widenings of his own, and the Setup door's brain list gained
**wici**:

- **Whole-system rule** (Zak's words: a GPU path that leaves the
  CPU empty "is not system requirement spirit — the system wants
  the whole system to function and process faster, not just select
  parts"). `plan["wici"]["legs"]` assigns every slot: chat → GPU
  leg, unsplit (dense work does not seesaw); reason → the fulcrum
  seesaw across both legs; summarizer → CPU leg by default, so no
  leg idles while the other works.
- **The split as overclock, with patience cost.** The reasoner is
  sized against the combined VRAM + RAM pool and split at
  β\* = Rc/(Rc+Rg) under a declared ASSUMED rate model
  (GPU 100 units; CPU 6.25/core). `patience_cost` prices the
  trade in numbers: against a resident all-GPU path, the SSD
  feed leg usually sets the pace, and the delta rides the plan
  and the declared limits. On the reference profiles it computes
  +114.3% reason-token latency — the feed, not either processor,
  is the long pole, exactly as the faux-split run found.
- **Free-range inversion.** Leadership follows the rates, never a
  fixed GPU-first rule: a 32-core box with a 4 GB card computes
  β\* = 0.667, the CPU leg leads the experts, and the plan says
  so in those words.
- **Faux stays faux.** InferSSD is CUDA-only; on any non-Nvidia
  box the plan computes and prints the whole split — and emits
  no engine, model, or seesaw step. The word FAUX rides the
  brain step, `plan["wici"]["faux"]`, the declared limits, the
  client summary, and the dry run.

Gate: 130 tests (119 v1 + 11 new in `tests/test_wici.py`),
compileall clean, census unchanged — the same six proposals
standing, no new findings, no fills.

## Addendum — observer mode and the personal Joy profile (2026-11-14)

Two more pieces landed the same night, both run for real before
they were written down:

- **Observer mode.** AI Core runs headless on a small VM: the
  eight ring services with no client, plus a snapshot loop
  writing one resource line a minute — the app keeping a
  flowing floor of its own host. Measured, not projected: the
  services idle at ≈103 MB together, the loop ≈12 MB, and
  "up" means 8/8 real protocol pings plus snapshot lines on
  disk. It is a second witness in the room — an additional
  angle for impromptu discussion. Its limits ride on its face:
  plain processes, not systemd units, so a host restart stops
  the watching, and one start script brings it back. Full
  method: both instruction docs.
- **The personal Joy profile.** Under the owner's grant, the
  Joy Calculator's intake can be answered from the owner's own
  data and conversation history — every answer cited and
  marked Direct or Practice, statements the record doesn't
  settle left UNANSWERED, an explicit cannot-answer list kept.
  The profile and its Q&A sheet are house data and stay home;
  the method ships in the instructions, the profile never does.

Both run under the night's operating rule, in the owner's
words: YOLO — confidence gradient, comfort and patience can
have most fun we can offer. Latitude follows measured
agreement, announced privilege steps, and things forming at
their own rate.
