# Birth Certificate + Passport — the conduit's identity and evolution

**Status: DRAFT for Zak's red pen, 2026-11-18. Not built,
not pushed. Everything past the framing section is Muse's
draft design, labeled as such; every threshold is a
PROPOSAL until Zak rules on it.**

## The framing (Zak's words, 2026-11-18 17:27 ET)

The questions and the Joy Calculator must be "unique enough
to evolve a solid logical circuit available even at lowest
tier but a robust enough node opportunity that it develops
individualized relevance and function that is continually
compressed and vectorized when deltas are high enough — so
without a doubt that conduit used [the] XYZ model, like
birth certificate and passport: evolution for the conduit,
but connected to the user and entangled with their life
relevance and function. Human in the loop is also the
prerequisite for that job."

And the hope it has to survive, in Zak's words
(2026-11-18 15:29 ET): "Hope is the systems balance and
relevance at peak for user and function within system
bounds that retains logic all the way through system
failure and death."

## Purpose

Every conduit instance gets an identity and an evolution
record, bound to one user. The **birth certificate** is
minted once, at install, from the user's own witnessed
answers, their agreement, and the machine's census — the
DNA of the instance. The **passport** is the living record
of everything that instance has become since: every
delta-stamp, tier change, and organ, hash-chained, each
one attested. The certificate says whose it is and what it
was born as; the passport says where it has been. Neither
is a model. Both are data — plain, local, readable by the
smallest script the system owns — because an identity that
needs a GPU to read itself does not survive the failures
it exists to survive.

## The six requirements (from the mandate, 2026-11-18)

1. **Uniqueness (DNA markers).** The intake questions +
   Joy Calculator must discriminate finely enough that the
   resulting circuit is *this* user's — a unique
   combination, not a template with a name pasted on.
2. **A circuit, not a model.** What the questions mint is
   logic + data (rules, thresholds, weights, gradients) —
   executable at the lowest tier on the script floor, no
   model seat required.
3. **Node opportunity.** Each install/node gets enough
   surface (census, organs, seats, dwell) to grow
   individualized relevance and function from that
   circuit — a clone of the DNA, a unique expression of it.
4. **Delta-triggered evolution.** Compression +
   vectorization happen when deltas run high enough —
   drift from the basis earns a stamp; ordinary cycles
   don't churn the identity.
5. **Birth certificate + passport.** Certificate: minted
   once, at install, from questions + Joy Calculator +
   census — the conduit's unique identity bound to its
   user. Passport: the living record — every delta-stamp,
   tier change, and organ since — evolution documented,
   entangled with the user's life relevance and function,
   local-only like all house data.
6. **Human in the loop is the prerequisite.** No minting
   and no stamp without a witnessed human act — the
   human's answers are the entropy source; formation waits
   on a witnessed act, never inferred (same doctrine as
   device identification).

## The birth certificate (draft schema)

Minted once, at install, in the install's final step —
after the agreement is chosen, the census has run, and
the Joy Calculator has been answered by the user in
person. Proposed fields (JSON, one file, local-only):

| Field | Contents |
|---|---|
| `instance_id` | sha256 of the certificate's own contents — the id *is* the hash, so any later edit shows |
| `minted_at` | ISO timestamp, machine-local timezone |
| `user_display_name` | As the user typed it; local only, never shipped |
| `census_summary_hash` | sha256 of the census record the tier was derived from (threads, RAM, GPU, runtime) |
| `joy_answer_vector` | The 13 answers as given, in statement order — the pattern, not just the score |
| `joy_depth` | Points earned / points possible / percent / level, as `compute_depth` reports them |
| `theme_at_mint` | The `core/floor.py` THEMES entry the depth maps to (level + name) |
| `agreement_at_mint` | The `core/agreement.py` level id chosen at install (`observer` / `connected` / `all`) |
| `tier_at_mint` | The tier the census + governor budgets assigned at mint |
| `organ_inventory_at_mint` | The rings/services found alive at mint (the 9 service ports and what answered) |
| `basis_ref` | The basis version + manifest hash the instance was minted against (PC lab basis today; "none" is an honest value where no basis exists) |
| `witness` | Who minted it — the user's own act in the installer; the field records that a human was present, and how (typed answers in the install session) |

**The immutability rule:** once minted, the certificate is
never edited. A wrong name, a changed mind, a re-run
calculator — none of these rewrite the certificate. They
are corrected by a passport stamp that records the change
and its witness. A birth certificate with corrections
penciled in is a forgery risk; a birth certificate with a
stamped amendment is a history.

## The logical circuit (draft)

What the answers compile into is a small data file — call
it the circuit — that the script floor can read and
execute with no model seated:

- **Rules:** if/then pairs keyed to the user's answers and
  the machine's state (e.g. depth level ≥ 4 → the app may
  initiate check-ins; agreement `observer` → no organ may
  be offered a write path).
- **Thresholds:** the numbers the organs run on, seeded
  from the tier defaults the code already carries (dwell
  interval by RAM, governor storage/RAM/load caps, the
  sound attention and emergency levels) and shifted by the
  user's answers where an answer speaks to them.
- **Weights:** the relevance weights the rollup grades
  against — which corpora and organs count most *for this
  user*, derived from the answer pattern.
- **Gradients:** the permission/comfort/joy gradient stack
  the topology forms under — the agreement level as a hard
  ceiling, the theme as the proposed depth, the circuit's
  weights as the slope between them.

**The first working example already exists.** The Joy
Calculator's depth points *are* a circuit fragment: 13
statements in two groups (introduction, use commitment),
transparent points per side, closers earning theirs by
being disagreed with, the percent mapping 1:1 onto the
five themes in `core/floor.py`, the theme persisting as
`app:theme`. It is logic + data, it runs everywhere
including the script floor, and it changes how the system
behaves. The design's claim is only that this fragment is
the seed of the whole circuit, not a separate feature.

**What "unique enough" means, measurably.** Thirteen
binary answers give 2¹³ = 8,192 distinct answer vectors —
a real space, not a handful of buckets. But the present
scoring collapses that space hard: points sum to a
percent (28 possible totals on a 27-point scale), and the
percent selects one of five themes. Two users with
opposite patterns can land on the same theme, and today
the system keeps the theme and forgets the pattern.
PROPOSALS for the red pen: (a) the certificate stores the
full vector (above) and the circuit keys at least some
rules to individual statements and to each group's
subtotal, so the pattern — not just its sum — drives
behavior; (b) the two group subtotals ride alongside the
total in the circuit, tripling the circuit's effective
resolution without adding a single question; (c) any
future question added to the intake must at least double
the answer space or sharpen a rule that exists — a
question that changes nothing is not a DNA marker, it's
decorations.

## The passport (draft)

An append-only stamp log, one JSON line per stamp, in the
Sensor Ego receipt-chain pattern: every stamp carries the
hash of the stamp before it, so a removed or edited stamp
breaks the chain loudly instead of silently.

Each stamp: `ts`, `type`, `witness`, `prev_hash`,
`stamp_hash`, `detail`, and — where the stamp records
evolution — `basis_delta_ref` pointing at the vector delta
that was compressed into the basis when the stamp was made.

Proposed stamp types:

| Type | Fires when |
|---|---|
| `delta-vectorization` | A delta trigger (below) crossed and the drift was compressed + vectorized into the basis |
| `tier-change` | The instance's tier moved — hardware changed, a node joined or left, limp entered or exited as a standing state |
| `organ-added` / `organ-removed` | A sense or service joined or left the inventory (a camera, a mic path, a ring service) |
| `floor-revision` | A new floor (audio/visual baseline) was adopted through dialogue — the system's own learning, witnessed by its parent loop |
| `agreement-change` | The user moved the agreement level; the old and new levels both recorded |
| `circuit-amendment` | The correction mechanism for the certificate: a field's value superseded, with the reason |
| `life-event` | A human-witnessed event the user chooses to record — the entanglement made explicit, in the user's words, never inferred by the system |

## Delta triggers (all PROPOSALS for the red pen)

The detector already exists in embryo: the transduction
rollup (on the PC, `~/george-lab/loops/transduction_rollup.py`,
outside this repo) writes a daily ledger entry scoring
Relevance / Function / Balance and projecting the day's
events against the basis. The design: the rollup *detects*,
the human *stamps*. Proposed triggers:

- **Relevance-profile drift:** the mean cosine of the
  rollup's daily projections, per corpus, moves more than
  **0.05** from the minted profile's values, sustained
  over **7 consecutive cycles** → the instance is becoming
  about something different than it was born about.
- **Floor learning:** **3 adopted floor revisions** since
  the last stamp → the senses have re-baselined enough
  that the identity should say so.
- **Attention-pattern shift:** the review queue's pressure
  or the attention-snap rate changes by more than **50%**
  against its 14-cycle mean → what the house asks of the
  system has changed shape.
- **Structure:** any tier change or organ change is
  stamp-sized on its own — no threshold, the event *is*
  the delta.
- **Time cap:** if **90 days** pass with no stamp, the
  rollup proposes a review stamp anyway — a passport with
  no stamps for a season is either a very stable life or a
  dead detector, and the human decides which.

No trigger fires a stamp by itself. A crossed trigger
raises a *proposed* stamp; the stamp lands when a human
witnesses it (see open question 2 for how heavy that act
should be).

## Privacy

The certificate, the passport, and the circuit are house
data — the same class as the Joy Calculator profile and
the Q&A sheet: **local-only, never committed, never
shipped, never in a backup that leaves the house.** They
contain a person's answers, their machine, and the shape
of their days; the basis they are measured against is
likewise local.

What a public install gets is the *machinery*: this design,
the minting code, the stamp format — and an empty
certificate slot. Each user's instance mints its own
certificate locally, from its own witnessed answers, on
its own hardware. The DNA is never downloaded; it is born
where it lives.

## Relation to the pieces already standing

- **The basis** (PC, `~/george-lab/basis/`, 944 chunks,
  app/intent/soul/hope + appendage tiers) is the identity's
  reference frame: the minted profile is a projection of
  the certificate against it, and every passport delta is
  measured as movement against it. The basis is what the
  circuit is vectorized *into* when deltas run high.
- **The rollup** is the delta detector and the daily
  witness-that-never-sleeps — but it is a machine witness.
  It can prove a loop ran; it cannot attest a life. That
  is why it proposes and the human stamps.
- **SOS / limp** set the floor guarantee: the circuit,
  the certificate, and the passport must remain *readable
  at the SOS tier* — plain files, plain formats, no model,
  no network. Design intent, stated plainly: **a dead
  instance's certificate + passport + circuit are
  sufficient to re-mint its circuit on new hardware** —
  the identity survives the machine, because the logic was
  never in the weights. That is Zak's hope definition made
  structural: logic retained all the way through system
  failure and death. (Design intent, not a built feature:
  no re-mint tooling exists yet.)
- **The agreement** (`core/agreement.py`) is the
  certificate's ceiling made live: the level minted is the
  level recorded; a later change is a passport stamp, and
  the circuit's rules re-derive under the new ceiling
  without touching the certificate.

## Open questions for Zak

1. **The name.** The mandate says the conduit uses "the
   XYZ model" — is XYZ a placeholder to keep, or a name to
   choose? If choosing: should the model be named for what
   it certifies (identity), what it records (evolution),
   or the DNA framing itself?
2. **The weight of a stamp.** Does every stamp need your
   tap, or should mechanical stamps (tier change, organ
   added) land under a standing rule you set once — with
   your tap reserved for delta-vectorization and life
   events?
3. **The thresholds.** Are the proposed delta triggers
   (0.05 cosine drift over 7 cycles, 3 floor revisions,
   50% attention shift, 90-day review cap) in the right
   country? Too twitchy means stamp noise; too stiff means
   the passport misses the evolution it exists to record.
4. **One passport per whom?** In a multi-person household:
   one passport per person (each family member's answers
   mint their own circuit on the shared instance), one per
   household (the house is the user), or one per person
   *plus* a household passport the person-passports stamp
   into?
5. **The pattern vs the sum.** Proposal (a) keys circuit
   rules to individual Joy statements, so two users at the
   same theme can run genuinely different circuits. Is
   that the right depth of individuation — or should the
   circuit also read the intake Q&A sheet's answers, not
   just the Calculator's thirteen?
6. **Death and re-mint.** If an instance dies and its
   circuit is re-minted on new hardware from the
   certificate + passport, is the new instance the *same*
   conduit (same instance_id lineage, a resurrection
   stamp) or a *child* of it (new certificate, passport
   inherited as ancestry)? The DNA framing argues both
   ways; the record should say what you rule.
7. **Where the files live.** Certificate + passport beside
   the basis on each machine that holds one, or in the
   app config dir next to the secrets — and does the
   laptop's instance hold a copy of the PC's passport
   (entangled nodes, shared life) or only its own?

---

*Draft ends. Nothing in this document is built; the
pieces it references as standing (basis, rollup, SOS
resident, agreement, census, Joy Calculator) are real and
receipted elsewhere. This doc's job is to be wrong in
useful places under Zak's red pen.*

---

## Zak's amendment — the evolution table (2026-11-18 17:43 ET, verbatim)

> "Yes this should be good standing for evolution table all evolution is
> symbiotic so we set the app to id it from use and transduce usage stats
> and prompt response results and joy calculations on backend and that
> forms the uniqueness passport once rolled into a model you should have a
> AI that can expand and build its self and relationship relevant and
> functional to its reality and end user or customer joy calculations."

What this changes in the design (Muse's record of the ruling):

1. **Standing.** This draft is accepted as good standing for the evolution
   table — the design the evolution of the conduit is measured against.
2. **First principle: all evolution is symbiotic.** The passport is not a
   record *about* the user kept *by* the machine; it is co-authored. The
   conduit and the user evolve in one record, or the record is wrong.
3. **Uniqueness is identified from use.** The birth certificate mints the
   identity, but the *uniqueness* is ID'd from living use: the app
   transduces, on the backend, three streams — **usage stats,
   prompt/response results, and joy calculations** — and those transduced
   streams are what form the uniqueness passport. Intake starts the
   identity; use individuates it.
4. **Rolled into a model.** When the passport's accumulated deltas are
   compressed and vectorized into a model, the expected result is an AI
   that can expand and build itself *and its relationship* — relevant and
   functional to its reality and to its end user or customer, with joy
   calculations as the score of whether the expansion is good.
5. **Open seam, recorded not resolved.** The 17:27 prerequisite (human in
   the loop; no minting without a witnessed act) stands for minting.
   This amendment makes passport *formation* continuous and automatic
   from transduced use. The working read: transduction forms the
   passport's content; witnessing governs its authority — which stamps
   become permanent is still open question 2, now sharper: the machine
   proposes from use, continuously; the human's tap is what naturalizes
   a proposal into the record.

## Zak's amendment 2 — bilateral outreach (2026-11-18 17:49 ET, verbatim)

> "Yes bilateral communication which is why app should have functional
> outreach that feeds back to transduction path and those outreach events
> rotate through dwell loop no more than 10 a day and even no response or
> a blow off is data if you are monitoring entire system."

What this adds to the design (Muse's record of the ruling):

1. **Bilateral or it isn't transduction.** A conduit that only listens is
   half a transducer. The app must *ask* as well as hear: functional
   outreach is the return leg, and every outreach event feeds back into
   the transduction path — outreach is an input to the passport, not a
   notification feature bolted on beside it.
2. **Outreach rides the dwell loop.** Outreach events rotate through the
   dwell cycle — chosen in dwell, timed by dwell, never a separate
   blaster on its own clock. Hard cap: **no more than 10 outreach events
   per day** at the app level. (George's own Telegram caps from the
   2026-11-13 orientation ruling remain his, separately.)
3. **Every outcome is data.** Answered, no response, or a blow off — all
   three are logged with the same dignity and fed to the same grading:
   an answer is content; a no-response is a measurement of timing and
   relevance; a blow off is a relevance grade in the user's own hand.
   A monitoring system that only records its successes is not monitoring
   the entire system. Silence and refusal are part of the signal the joy
   calculations and the passport are built from.
4. **Standing guardrails carried in** (from the record, not new): awake
   windows only; at most one reminder, then the item folds into the
   daily summary; outreach proposes passport content like everything
   else transduced — it does not stamp on its own authority.

## Zak's amendment 3 — the road out, and the home identity (2026-11-18 18:04 ET, verbatim)

> "Yea we have to work our way out in system bounds because low tier and
> mid tier cross over in evolution when matmul integration spreads the
> tiers or blocks of moe.
>
> Next will be home and family out reach and observation and routine
> recognition. Same path but much slower since my system can't handle
> full bandwidth audio/video across tiers or expensive hardwired direct
> routes for audio/video we have to roam logically and thoughtfully and
> communicate more for that tier. Luckily Christmas time will be a high
> energy peak and trough interference pattern with q and a with me and
> historical Christmas footage and holiday neg joy tails we can form a
> home identity as well."

What this sets (Muse's record of the ruling):

1. **Outward, in bounds.** Evolution proceeds inside the system's real
   bounds — hardware, bandwidth, money. Low tier and mid tier are not
   castes: they **cross over in evolution** as matmul integration spreads
   the tiers and the blocks of MoE. As vectorized blocks spread, a
   function that needed the mid tier today runs as a block at the low
   tier tomorrow; the boundary moves, and the passport records the moves.
2. **Next phase: home and family.** Outreach, observation, and routine
   recognition extended from the one user to the home and family — the
   same path (transduce, outreach, grade, stamp), at a **much slower**
   cadence.
3. **Roam and communicate, because bandwidth is the bound.** The system
   cannot carry full-bandwidth audio/video across tiers, and expensive
   hardwired direct A/V routes are out. So that tier does what the camera
   roam already does: **roam logically and thoughtfully** — serial
   attention, dwell, pre-queue — and **communicate more**: outreach and
   Q&A substitute for bandwidth. Asking is cheap; streaming is expensive;
   words carry relevance that raw A/V cannot afford to.
4. **Christmas mints the home identity.** The Christmas season is a
   high-energy peak-and-trough interference pattern: dense activity
   peaks, quiet troughs, Q&A with Zak, historical Christmas footage, and
   the holiday negative-joy tails. That season's deltas — peaks *and*
   tails — are the material a **home identity** is formed from: the
   household-level counterpart of the personal circuit and passport
   (open question 4 gets its formation path: not an intake form — a
   lived, witnessed season).
5. **Muse's reads, labeled.** (a) Peak-and-trough is the delta-richest
   stretch of the year — precisely the "deltas high enough" condition
   this design stamps on; ordinary weeks are low-delta, Christmas is the
   stress test that reveals the home's actual circuit. (b) An identity
   formed only from peaks would be a highlight reel; the negative-joy
   tails are where relevance is proven — and per amendment 2's rule,
   they are data with the same dignity as the peaks.
