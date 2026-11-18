"""Learn — the education layer, and the explainers that ride the UI.

Two surfaces, one content model, three reading layers everywhere:

  plain   what this does, in ordinary words
  story   where it came from — the back story, told in place
  tech    the receipts: rings, ports, beats, measured things

SECTIONS is the Learn view: one entry per feature, each carrying all
three layers. EXPLAINERS is the hover/pop-up registry: short texts
keyed by the control they explain, in the same three layers. The
client sets the layer from the Learn view's toggle; dynamic tooltips
compose the explainer with live state the client actually has (a
service's up/down, the floor's last snapshot) — this module never
invents live values.

⚠ ALL WORDING IS DRAFT — Zak's plain register, for his red pen,
like every other user-facing string on this branch.
"""

LAYERS = ("plain", "story", "tech")
LAYER_NAMES = {"plain": "Plain", "story": "Back story", "tech": "Technical"}

# --- The Learn view: back story told in place, by feature -------------

SECTIONS = [
    {
        "id": "joy-calculator",
        "title": "The Joy Calculator",
        "plain": "A short set of plain statements you agree or "
                 "disagree with. The pattern of answers sets how deep "
                 "the relationship with the AI side begins — from "
                 "just a chatbot and reminders, up to a presence "
                 "woven into your days. Nothing is submitted; every "
                 "answer is handed to the back end the moment you "
                 "give it.",
        "story": "It began as a question, not a settings page: how "
                 "deep should this relationship START? Most software "
                 "decides that for you, in a EULA you never read. "
                 "The calculator asks instead, in sentences a person "
                 "can actually answer, and it only sets the "
                 "beginning — where it goes from there, time tells.",
        "tech": "Thirteen statements in two groups (introduction, "
                "use commitment), each carrying transparent depth "
                "points per side; closers earn theirs by being "
                "disagreed with. Answers stream to the memory ring "
                "(9108) under joy:<session>:<sid> as given; the "
                "depth outcome maps 1:1 onto the app theme "
                "(core/floor.py THEMES) and persists as app:theme.",
    },
    {
        "id": "base-floor",
        "title": "The base floor",
        "plain": "Under every theme — even the plainest — the app "
                 "quietly checks that its own parts are really "
                 "there and really what they claim to be. It checks "
                 "when the app opens, and again on a slow background "
                 "beat. At no other time. What it finds is written "
                 "down, down parts and all.",
        "story": "The monitors used to shout constantly — every "
                 "check a siren, every siren a habit of ignoring "
                 "them. So the floor learned restraint: a system "
                 "that checks itself without rest teaches itself "
                 "anxiety. Now alignment breathes on wake and dwell "
                 "only, the way a person glances at the locks on "
                 "the way to bed — not by staring at the door.",
        "tech": "Wake beat on open + dwell beat every "
                "DWELL_INTERVAL (Options → Patience; default 15 "
                "min). Each beat probes {\"action\": \"health\"} on "
                "all eight ring services and compares service / "
                "ring / port against the expected map "
                "(core/floor.py EXPECTED_SERVICES). Snapshots land "
                "in memory under floor:<session>:alignment; aligned "
                "means nothing down and nothing mismatched. Web is "
                "the standing exception: its health probes internet "
                "reachability, so its identity is taken by ping.",
    },
    {
        "id": "floors-gradients",
        "title": "Floors and gradients",
        "plain": "A floor is a living baseline: what a sense usually "
                 "sounds or looks like, learned from the place "
                 "itself. Things are noticed by how they rise off "
                 "the floor — and nothing is called an event until "
                 "the floor itself is steady enough to judge.",
        "story": "This came from the Sensor Ego in the basement "
                 "lab: an ear and an eye watching a real house. The "
                 "first versions detected first and learned later, "
                 "and cried wolf at every radiator tick. The law "
                 "that fixed it: flowing floor first — a rolling "
                 "baseline with an inverse — then the active plane "
                 "where events grade, then agreement across "
                 "witnesses before anything hardens into record.",
        "tech": "Descriptors only; no raw retention beyond a "
                "bounded control ring. Sound: 5-second quanta, "
                "floor and inverse floor both ARMED from rolling "
                "windows, learn-only-from-non-burst. Video: a "
                "3-hour confidence gradient — native at the fresh "
                "edge, stepping down geometrically with age, burst "
                "segments pinned native. Compression follows the "
                "gradient, not a flat clock.",
    },
    {
        "id": "redundancy",
        "title": "Redundancy — the night the thread wouldn't start",
        "plain": "If one part of the system dies, the rest step "
                 "down a named rung and say so. A dead brain is an "
                 "event, not the end of the organism. Silence — a "
                 "part failing and nothing saying so — is the only "
                 "unforgivable failure here.",
        "story": "On 2026-11-13 the lab PC's process table filled "
                 "with a flood of stray desktop tasks — over a "
                 "hundred thousand of them — until the chat brain "
                 "could not start a single thread to answer with. "
                 "The gateway lived; the model door was nailed "
                 "shut. But the ears, the eyes, the floors and the "
                 "receipts on the little Pi never stopped for a "
                 "minute. The lesson got written into the design: "
                 "control pipes keep reserved room, runaway organs "
                 "cap themselves, and the harness is graded on what "
                 "it does while its brain is down.",
        "tech": "Self-contained redundancy first: critical paths "
                "run on the owner's own stack; cloud is an "
                "enhancement, never a load-bearing wall. Per-slot "
                "fallback chains degrade local → second local → "
                "free tier → paid, each step written down and "
                "announced at the next check-in. The floor's dwell "
                "snapshots keep recording alignment through an "
                "outage — the record of the bad night is itself a "
                "receipt.",
    },
    {
        "id": "free-tier",
        "title": "Free-tier optimization — the gatekeeper bypass",
        "plain": "Local first, because local is free and it's "
                 "yours. Free tiers absorb the wide, cheap work. "
                 "Paid is a deliberate decision, made on evidence "
                 "and written down — never the default the app "
                 "drifts into.",
        "story": "The standing rule of the lab: never lead with "
                 "\"just pay for it.\" Find the clever free path. A "
                 "kid in a basement should be able to replicate "
                 "this whole system — that is the standard it is "
                 "built to, not a discount it apologizes for. The "
                 "summarizer eats the breadth, the reasoner works "
                 "on the slow beats, and the expensive mind is "
                 "spent only where a gate says it earns its keep.",
        "tech": "Routing is by measured cost: tok/s and context "
                "are measured per model, not believed from a label. "
                "The cloud group in Options carries the policy "
                "(never / draft / allowed) and a per-session budget "
                "for paid answers; core.models enforces both at "
                "chat time and reports every block in the open. "
                "Token budgets are floors and gradients, not vibes.",
    },
    {
        "id": "plugs",
        "title": "Plugs, not plumbing",
        "plain": "New parts plug in; they don't get plumbed in. A "
                 "new tool, a new sense, a new model — each one "
                 "arrives, says what it is, and starts answering "
                 "to its name. The app grows its controls from what "
                 "the part reports about itself.",
        "story": "Every generation of this system began as one "
                 "person soldering one more capability onto a "
                 "growing machine, late at night, until the machine "
                 "was mostly solder. The plug contract is the "
                 "promise that the next part — whoever's it is — "
                 "costs an afternoon, not a rewrite.",
        "tech": "One wire contract everywhere: one JSON object per "
                "connection, {\"action\": ...} in, {\"status\": "
                "...} out; ping → pong; health → the transductive "
                "self-report {service, ring, port, uptime_s} from "
                "the shared scaffold (core/ring_service.py). A new "
                "service dropped in a ring folder registers, "
                "serves, and is picked up by the floor on the next "
                "wake or dwell beat.",
    },
    {
        "id": "models",
        "title": "Models from any angle",
        "plain": "A model can arrive from anywhere — the machine "
                 "you're sitting at, a router preset, a box across "
                 "the room, a free tier across the internet. Each "
                 "slot keeps an ordered stack of them; the first "
                 "one that can actually answer, answers.",
        "story": "George, the lab partner this app grew around, "
                 "has run on whatever mind was at hand: cloud "
                 "freebies, a 7B on the desk machine, a 30B on the "
                 "slow deep beats. Once, when his own box went "
                 "down, his prime — the soul, the skills, the live "
                 "state — was worn by a different mind entirely, "
                 "and the discipline held. The mind is a plug. The "
                 "harness is the partner.",
        "tech": "Slots: chat, reason, summarizer (core/models.py). "
                "Entries are Ollama models or OpenAI-compatible "
                "endpoints; stacks persist as app:model-stacks. "
                "Resolution probes in stack order and reports "
                "every verdict — served, unreachable, "
                "model-missing, blocked by policy or budget. Only "
                "the chat slot has a caller today; the page says "
                "so, in the open.",
    },
    {
        "id": "the-game",
        "title": "The Eddy Toy",
        "plain": "A quiet pond. Poke the water; eddies spin up, "
                 "drift, bump, and now and then merge into one big "
                 "wobbling eddy wearing disco colors. No score, no "
                 "timer, no losing. That's the whole game, on "
                 "purpose.",
        "story": "The night this version was designed, two disco "
                 "balls got plugged in somewhere in the house and "
                 "the basement eye never saw a flicker of them — "
                 "every zone, all evening, flat zero. The toy is "
                 "where their colors went. It is also the one room "
                 "in the house with no harness: nothing it does is "
                 "graded, recorded, or evidence about anyone.",
        "tech": "A GTK DrawingArea and a gentle tick. The physics "
                "is a pure step function (core/toy.py) with no I/O: "
                "nothing is persisted, nothing is sent to the "
                "memory service, no snapshot ever names it. It "
                "opens, you poke it, it is silly, you close it.",
    },
    {
        "id": "first-run",
        "title": "First run on a fresh box",
        "plain": "Point the app at a plain Linux install and it "
                 "threads itself through: it looks at the hardware, "
                 "announces the whole cost up front — disk, "
                 "downloads, time, what needs the network, what "
                 "costs money (nothing, by default) — and then "
                 "works the plan one consented step at a time. "
                 "There is a home-folder minimum mode that changes "
                 "nothing outside your own folders.",
        "story": "The lab's installs used to be folklore: commands "
                 "in chat scrollback, a sudo prompt appearing like "
                 "weather. The Setup door is the folklore written "
                 "down and made honest — privilege as a comfort "
                 "gradient you climb by pressing buttons, the "
                 "exact command on the table before anything runs, "
                 "and a dry-run that prints the whole script for "
                 "anyone who'd rather read than trust.",
        "tech": "core/setup.py: profile probes are read-only "
                "(os-release, cpu, meminfo, lspci/nvidia-smi when "
                "present, disk). Plan steps are data — title, "
                "exact commands, privilege floor, network/disk/"
                "time costs. Model sizing reads cores + RAM + "
                "VRAM, not memory alone. Pairing writes an "
                "exportable script that installs a pasted public "
                "key with a tailnet-only from= restriction.",
    },
    {
        "id": "self-maintenance",
        "title": "The app maintains itself",
        "plain": "On the same wake and dwell beats as the floor, "
                 "the app runs a census: does what it advertises "
                 "match what its services actually do? Do the docs "
                 "match the wire? Does anything read the config "
                 "values the config offers? Purely mechanical "
                 "mismatches get repaired with a receipt and a "
                 "backup. Everything else becomes a written "
                 "proposal — the owner's red pen decides.",
        "story": "Zak's word for the quarry is gloss: the detail "
                 "that doesn't align with the rounded plan, the "
                 "one that trips you at midnight. This build's own "
                 "census found real ones the day it was written — "
                 "tool names the client advertised that the "
                 "services had never implemented, a config whose "
                 "numbers nothing read. The census exists so the "
                 "next gloss is found by the machine that made "
                 "it, on a beat, in the open.",
        "tech": "core/selfmaint.py compares declared surfaces: "
                "client TOOL tokens vs service handler tables "
                "(AST), README tokens and ports vs core.protocol, "
                "config keys vs actual reads, ring folders vs the "
                "registry, explainer coverage. Safe fills are "
                "contract-derivable and idempotent; findings "
                "dedupe by id; proposals accumulate under "
                "selfmaint/proposals/ and are never auto-applied.",
    },
    {
        "id": "hybrid",
        "title": "Parent, daughter, hybrid",
        "plain": "One install can wear three shapes. A daughter "
                 "is senses and briefs on a small box: it watches "
                 "its own floors and, on the dwell beat, sends its "
                 "parent a short signed brief — never raw sound or "
                 "pictures. A parent is the full app, keeping the "
                 "house's record and reading its daughters' "
                 "briefs. A hybrid is both on one box, talking to "
                 "itself — the shape you test with.",
        "story": "This is the Sensor Ego pattern in miniature: "
                 "the little Pi in the basement has been living "
                 "as a daughter all along — ears and eyes out "
                 "there, judgment and memory up here, hash-linked "
                 "receipts between them. v1 ships the skeleton "
                 "honestly: real chain, real briefs, real queueing "
                 "when the parent is down. The full v3 stack — "
                 "graded consensus, the subconscious pass — is a "
                 "named expansion path, not a claim in this box.",
        "tech": "core/hybrid.py: briefs are {seq, ts, floor "
                "summary, chain head}; the chain is sha256-linked "
                "(seq, ts, prev-hash). Transport is the existing "
                "wire — a memory `set` under daughter:<id>:brief "
                "on the parent's endpoint; unreachable parents "
                "mean a local queue that drains on reconnect. "
                "The floor's snapshots carry each paired "
                "daughter's brief age and staleness.",
    },
]

SECTION_BY_ID = {s["id"]: s for s in SECTIONS}

# --- Explainers: hover / pop-up texts keyed by control ----------------

EXPLAINERS = {
    "theme": {
        "plain": "The relationship the app proposes on opening — "
                 "set by the Joy Calculator, or taken plain, "
                 "head-on, from the calculator tab.",
        "story": "Depth used to be a number in a summary nobody "
                 "re-read. Now it is the coat the app wears: the "
                 "theme is the relationship, proposed fresh every "
                 "opening, changeable any time.",
        "tech": "Persisted in the memory service as app:theme; "
                "stamped into every floor snapshot so alignment "
                "is always read against the standing relationship.",
    },
    "floor": {
        "plain": "The base floor's latest word: whether every "
                 "ring service is home and is what it claims to "
                 "be. Checked on wake and on the dwell beat only.",
        "story": "The floor learned restraint — it breathes "
                 "instead of shouting. A down organ found here is "
                 "the monitor doing its job, not the app failing.",
        "tech": "Source: the FloorMonitor's last snapshot "
                "(floor:<session>:alignment in memory). aligned = "
                "nothing down, nothing mismatched, field by field "
                "against the expected map.",
    },
    "model": {
        "plain": "Who answers in chat. The stack's first reachable "
                 "entry serves — see the Models view for the whole "
                 "stack and its report.",
        "story": "The mind is a plug: George has answered through "
                 "several, and once through a borrowed one, and "
                 "stayed himself. Pick the plug; the harness keeps "
                 "the partner.",
        "tech": "core.models.resolve_chat_entry probes the chat "
                "stack in order (Ollama /api/tags; endpoint "
                "/models), applies the cloud policy and session "
                "budget, and returns a per-entry verdict list.",
    },
    "ring": {
        "plain": "One organ of the system: green when it answers, "
                 "red when it doesn't. The dot is a display — the "
                 "floor's snapshots are the record.",
        "story": "Each organ sits in a ring: state holds what "
                 "must persist, actuation touches the machine, "
                 "atmosphere faces the world and takes the weather "
                 "first.",
        "tech": "Dots poll by TCP connect on the Options → "
                "Cadence beat. Health proper is the transductive "
                "report: {service, ring, port, uptime_s} via "
                "{\"action\": \"health\"}.",
    },
    "calculator": {
        "plain": "Agree or disagree with plain statements; the "
                 "pattern sets where the relationship begins. "
                 "Skip, End, and Finish later are always in the "
                 "row — the exits never hide.",
        "story": "It asks instead of deciding for you — and only "
                 "sets the beginning. Where it goes, time tells.",
        "tech": "Answers stream per-answer to memory "
                "(joy:<session>:<sid>) with a running depth "
                "snapshot; an unfinished run is offered back on "
                "the next opening.",
    },
    "toy": {
        "plain": "Poke the water. Eddies happen. Nothing is "
                 "kept, scored, or sent anywhere.",
        "story": "The disco colors the basement eye never saw, "
                 "living where they belong: in the one un-"
                 "harnessed room of the house.",
        "tech": "Pure step physics (core/toy.py), in-memory only. "
                "No memory-service writes, no floor snapshots, no "
                "telemetry — by construction, not by policy.",
    },
    "setup": {
        "plain": "The first-run thread: the app looks at the box, "
                 "says out loud what it will cost, and only touches "
                 "what you hand it — one consented step at a time.",
        "story": "Too many installers are a leap of faith with a "
                 "progress bar. This one was designed the way the "
                 "lab learned to work: readback first, exact "
                 "commands on the table, privilege as a gradient "
                 "you climb by pressing buttons, never a grab.",
        "tech": "core/setup.py builds the plan as pure functions "
                "over a read-only hardware profile. Steps carry "
                "their privilege floor; rendering the dry-run "
                "script is the same data the executor runs — what "
                "you read is what runs.",
    },
    "selfmaint": {
        "plain": "On wake and dwell the app compares what it "
                 "says about itself against what is actually "
                 "there, repairs the purely mechanical mismatches "
                 "with receipts, and files the rest as proposals "
                 "for the owner's red pen.",
        "story": "Born from a day of finding the gloss by hand: "
                 "the client advertised tool names the services "
                 "never implemented, the config held values "
                 "nothing read. A detail that doesn't align with "
                 "the rounded plan is a gloss; the census hunts "
                 "them so nobody has to trip over them twice.",
        "tech": "core/selfmaint.py: census over declared surfaces "
                "(client tokens, service handlers via AST, docs, "
                "config reads, explainer coverage). Safe fills are "
                "mechanical, backed up, idempotent; behavior "
                "changes are proposals under selfmaint/proposals/, "
                "never auto-applied.",
    },
}

# Explainers generated by self-maintenance fills (from a service's
# health self-report, when a live control lacks an entry) are merged
# in at runtime via register_generated(); hand-written entries above
# always win.
GENERATED = {}


def register_generated(entries):
    """Merge generated explainer entries {key: {layer: text}}."""
    for key, entry in (entries or {}).items():
        if key not in EXPLAINERS and isinstance(entry, dict):
            GENERATED[key] = entry


def section(section_id):
    return SECTION_BY_ID.get(section_id)


def explainer(key, layer="plain"):
    """The explainer text for a control, at a reading layer.
    Unknown keys explain nothing; unknown layers read plain."""
    entry = EXPLAINERS.get(key) or GENERATED.get(key)
    if entry is None:
        return ""
    return entry.get(layer) or entry["plain"]
