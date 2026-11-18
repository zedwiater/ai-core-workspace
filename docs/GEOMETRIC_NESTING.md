# Geometric Nesting

The tree is shaped like the system it describes: a balanced core,
rings of coherency around it, and an atmosphere that faces the world.
Geometry changes; the wire contract does not.

## The map

| Architecture language | In the code |
|---|---|
| **Core** — balanced center everything shares | `source/core/` — `protocol.py` (the wire contract), `ring_service.py` (the service lifecycle), `loop.py` (Intercept & Compute), `intake.py` (Joy Calculator engine), `floor.py` (themes + the base floor) |
| **Rings of coherency** — layered services, inner rings hold state, outer rings touch the world | `source/rings/` — `state/`, `actuation/`, `atmosphere/` |
| **State ring** (inner) — holds what must persist, close to the core | `rings/state/` — memory (9108), coding (9107) |
| **Actuation ring** (middle) — acts on the machine itself | `rings/actuation/` — files (9101), shell (9104) |
| **Atmosphere** (outer ring) — world-facing; takes the environmental impact first | `rings/atmosphere/` — web (9102), vision (9103), sound (9105), voice (9106) |
| **Bilateral flow** — layers call inward and report outward on the same contract | The client calls services over the JSON wire protocol; services report back on the same connection. The Joy Calculator's writer streams answers *inward* to the state ring (memory) as they are given |
| **Transductive health** — every layer reports how it is doing, in-band | Every service answers `{"action": "health"}` with `{status, service, ring, port, uptime_s}` via the shared scaffold |

The client (`source/app/ai-client.py`) is the skin: a GTK window with
an "AI Core" chat tab and a "Joy Calculator" tab. All non-GUI logic lives
in the core so it can be tested headlessly.

## The nested lifecycle

Every ring service runs the same lifecycle, from
`core/ring_service.py`:

1. **Register** — bind its historical port under its name and ring.
2. **Serve** — accept one JSON request per connection, dispatch to its
   handler dict, reply, close. Errors return a response; they never
   kill the loop.
3. **Report** — answer `health` with its transductive health.

## The Joy Calculator tab

The Joy Calculator calculates the **starting depth of the relationship
between a person and the AI side**. It is not a form, and it does not
add up anything about money or work.

**The instrument:** paced pages. An introduction, then two groups of
explainer pages — *Introduction explainers* (what the AI side is, how
this works) and *Use Commitment explainers* (what the AI side would
do). Each explainer is one simple statement; the person answers
**Agree** or **Disagree**. Each statement explains a use commitment,
and the agree/disagree pattern sets how deep the relationship begins.

**The output:** a beginning-depth level and what that depth means the
AI side starts as. The scale runs between Zak's named poles —
shallow: *just a chatbot and neglected reminder app*; deep: *hyper
processing lives* — with three drafted depths between
(*A Helper When Asked*, *A Keeper of the Threads*, *A Companion in
the Loop*; the poles themselves are levels 1 and 5: *Just a Chatbot*
and *Hyper Processing Lives*). The summary page then says, in the
doctrine's own terms, that the calculator only sets the beginning:
where it goes from there, **time tells**. Scoring is transparent:
every statement carries its depth points for each side, closers earn
theirs by being disagreed with, and the summary lists what each
answer contributed.

**Default mode.** The tab's default mode (later modes hang off the
name) nudges by design: the descriptors and button labels are written
to spike curiosity — invitational copy that makes the next page feel
worth opening — and never to trap. Every page carries the same three
exits alongside Continue:

- **Skip** — pass on one statement. A skip is data: it streams to the
  memory service marked `"skipped"` (`joy:<session>:<sid>`) and
  counts as no-signal for depth — neither agree nor disagree.
- **End** — stop now. The summary computes the beginning depth from
  the partial pattern answered so far and says plainly that a partial
  read is a shallower read, naming how many statements it rests on.
- **Finish later** — a progress marker (`joy:<session>:progress`,
  mirrored at `joy:latest-progress`) keeps the person's place:
  page index plus answers so far. Reopening the tab with an
  unfinished marker in the memory service offers **Resume** (same
  backend session, answers and page restored) or **Start over**.

**Progressive engagement (unchanged mechanic):** there is no final
submit — each answer streams to the memory service **at the moment it
is answered** (`joy:<session>:<sid>`, plus a running depth snapshot
under `joy:<session>:depth`). If the memory service is down, answers
queue locally, drain when it returns, and the tab's status line says
so ("backend: N answers held").

**⚠ All wording is DRAFT.** Every statement, level name, meaning
line, nudge line, and the doctrine line in `core/intake.py` is draft
copy in Zak's plain register, pending his red pen. The statements are
a data-driven list (`STATEMENTS`) — revising the instrument is a
small edit to `core/intake.py` only.

## Themes and the base floor

**The depth becomes a theme.** Each Joy Calculator depth level maps
to a named theme the app runs under (`core/floor.py`, `THEMES`) —
the same five depths, worn as the app's standing behavior:

| Depth | Theme |
|---|---|
| 1 — Just a Chatbot | **Plain Chatbot & Reminders** |
| 2 — A Helper When Asked | **Helper on Call** |
| 3 — A Keeper of the Threads | **Keeper of the Threads** |
| 4 — A Companion in the Loop | **Companion in the Loop** |
| 5 — Hyper Processing Lives | **Hyper Processing Lives** |

The theme is **proposed as the relationship upon opening**: the
header reads `Relationship: <theme>`, the calculator's summary names
the theme the person begins under, and the choice persists in the
memory service (`app:theme`) so the next opening proposes the same
relationship.

**Plain is a default theme option, not a failure state.** Level 1 —
plain chatbot and reminder — is what the app runs under when no
theme has been set, and the calculator tab offers it directly
(**Start plain**): no run needed, no depth read taken. Plenty of
people want exactly that, and the app honors it as a theme in its
own right.

**The base floor, nested in every theme.** Underneath all five
themes, including plain, the back end still runs monitors for
**relational reality intelligence alignment — on wake and dwell
only.** Two beats, no others:

- **Wake** — once, when the app opens: the client asks all eight
  ring services for their live state (`{"action": "health"}`,
  reach-home-first) and compares the answers against the expected
  map — the name, ring, and port each service should report.
- **Dwell** — the same check on a periodic background tick
  (15 minutes by default, `DWELL_INTERVAL_S` in `core/floor.py`),
  on a lightweight timer thread that never blocks the UI and stops
  cleanly when the app closes.

Each check records an **alignment snapshot** to the memory service
under `floor:<session>:alignment`: the beat, a timestamp, the
standing theme, which services are up and which are down, and any
mismatches named plainly (a service reporting the wrong ring or
port). `aligned` is true only when nothing is down and nothing
mismatches. A service down or a mismatch found is the monitor doing
its job — it is written down, and the app keeps running. Web is the
documented exception in the comparison: its `health` predates the
ring convention and probes internet reachability, so its identity
is taken by `ping` when needed and up/down is all the floor checks
for it.

(The sidebar's colored dots are a pre-existing display indicator
polled by the chat pane; they are not the floor. The floor's
alignment snapshots happen on wake and dwell, and at no other time.)

**⚠ Theme names and behaves-as lines are DRAFT** copy too, in
`core/floor.py`, pending Zak's red pen like everything else
user-facing here.

## Invariants (unchanged by this restructure)

- Ports: files 9101, web 9102, vision 9103, shell 9104, sound 9105,
  voice 9106, coding 9107, memory 9108.
- systemd units: `ai-mcp-<name>.service`, same names, same ports.
- Wire protocol: one JSON object per connection —
  `{"action": ...}` in, `{"status": ...}` out; `ping` → `pong`.
- Model surface: `TOOL:<service>:<action>:{json}` tokens, unchanged.
- Every pre-existing action and its response shape, unchanged —
  including the web service's `health` action, which predates the ring
  convention and still probes internet reachability (so web is the one
  service whose `health` is not the transductive-health report; its
  ring position is reported by the other seven verbatim and by web's
  `ping`).
- The client still executes `TOOL:shell:exec` locally, as it always
  has; the shell *service* is unchanged for other callers.

## v1 additions (2026-11-13) — the doors, same geometry

The v1 build adds doors without moving the rings:

- `core/settings.py` — the Options store (memory key
  `app:options`): patience, cadence, senses, redundancy, cloud,
  hybrid role. Choices are validated against a declared table;
  the client wires each one to a live effect.
- `core/models.py` — per-slot model stacks (chat / reason /
  summarizer), Ollama discovery + OpenAI-compatible endpoints,
  probe/resolve with per-entry verdicts. The chat path serves
  from the stack; nothing is swapped silently.
- `core/learn.py` — explainers and Learn sections in three
  reading layers (plain / story / tech); the layer toggle drives
  every tooltip in the client.
- `core/toy.py` — the Eddy Toy's pure physics step. The tab is
  deliberately not wired to memory, the floor, or anything else.
- `core/setup.py` — the plan-first bootstrap engine: read-only
  hardware profile → step plan with totals, privilege levels
  0–3, dry-run script rendering, model sizing with a measured
  floor row, pairing-secret and pairer-script generation, config
  validation over the wire protocol.
- `core/selfmaint.py` — the census on the floor's beats:
  declared surfaces compared, mechanical safe fills with backups
  and receipts, everything else filed as proposals. Expansion
  rides these organs; a new service joins by label + route
  (`core/ring_service.parse_label` / `serve_route`), and the
  census is what notices.
- `core/hybrid.py` — the parent/daughter skeleton: hash-linked
  brief chain, sized briefs over the wire protocol, local queue
  with drain-on-reconnect, parent-side verification (age, stale,
  pair, chain). Not the full Sensor Ego v3 — see
  `docs/APP_EXPERIENCE_AND_HARNESS.md` for the honesty line.
- Client tabs: AI Core (calm surface), Joy Calculator, Options,
  Models, Learn, Setup, Eddy Toy. The floor gained two guarded
  companions on its existing beats — self-maintenance and the
  daughter runtime — and an optional daughters probe; no new
  beat exists.
- Tests: `tests/` (unittest, stdlib only) — 119 checks covering
  the wire protocol, floor, intake, loop, ring scaffold + labels,
  settings, model stacks, toy physics, setup plans, the census
  and its fills, and the two-instance hybrid.
