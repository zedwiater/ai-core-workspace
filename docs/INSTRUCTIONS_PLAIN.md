# AI Core — Instructions (plain language)

**The system is just a set of permission gradients leading to full autonomy.**

Every gradient in this build — the privilege comfort levels during
setup, the relationship depth you choose, the model tiers, the
trust between a parent and a daughter — is the same shape: consent
deepens in steps, each step is earned and announced out loud, and
the direction of travel is autonomy.

Status: DRAFT, in the owner's register, for the owner's red pen.

---

## What this is

A local-first AI app. It runs on your own machine, talks to small
models that live on that machine, and uses a ring of little services
("organs") for files, shell, web, cameras, sound, voice, code, and
memory. Nothing about it needs the cloud. Cloud endpoints can be
added as a backup rung — never as a requirement.

It has been run, for real, on a Chromebook with an Intel i3 and no
graphics card, using a small (1.5B) model carried entirely by
ordinary RAM. Slow, and working. That is the floor everything else
is sized from.

## Installing it

Two honest ways:

- **The guided way**: open the app, go to the **Setup** tab. It
  looks at your machine first (read-only), then shows you a plan
  with the full cost up front — disk, downloads, time, what needs
  the network, and money ($0 by default). You pick how much
  privilege you're comfortable granting (see "Approvals" below),
  and it walks the steps one at a time, with a receipt for each.
- **The script way**: `install.sh` in this repo does a system
  install to `/opt/ai-core` with systemd units. The Setup door's
  plan and the script come from the same logic.

The smallest footprint is the **home folder minimum**: everything
under `~/ai-core`, no system changes at all. The Setup plan states
both footprints before anything runs.

### Linux generally

- Debian/Ubuntu family: packages come through `apt`.
- Fedora family: `dnf`. Arch family: `pacman`.
- The plan picks the branch from your distro automatically; each
  package step is shown as the exact command before it runs.

### Arch specifically

- Same plan, `pacman` branch: `sudo pacman -S --needed python
  gtk4 libadwaita` class steps, each shown first.
- The app itself never touches your kernel, bootloader, or
  initramfs. If your machine's boot needs work (mkinitcpio hooks
  and friends), that is system surgery outside this app — do it
  with your distro's own tools, not from here.
- On Arch as everywhere else, user units under
  `~/.config/systemd/user/` are the no-sudo way to keep services
  breathing; the home-minimum install leans on exactly that.

## Adding a script (a new organ)

A script joins the build with two steps, and only two:

1. **Label its source.** Near the top of the file, a label block:

   ```
   # --- AI Core service label ---
   # Label-Name: memory
   # Label-Origin: ai-core-workspace build
   # Label-Version: 1
   # Label-Does: key/value memory over the wire protocol
   # --- end label ---
   ```

   (Inside the module docstring works too — same lines.)
2. **Route it.** The script's `serve("name", "ring", PORT, {...})`
   call must agree with the route table in
   `source/core/protocol.py` — same name, same port.

That's all. On the next wake or dwell beat, the app's
self-maintenance census notices the new organ and the floor starts
checking it. A script that is unlabeled or unrouted is not
silently switched on — the census files it as a finding, and the
label (being mechanical) can be backfilled by the app itself,
with a receipt. Joining the route table is a deliberate act: it
is a proposal until the owner says yes.

## Setting up models

Open the **Models** tab. There are three slots — **chat**,
**reason**, **summarizer** — and each is a *stack*: an ordered
list. The first entry that answers does the work; the rest are
the fallback order, shown on screen, never hidden.

- Models already installed in Ollama can be added from discovery.
- Any OpenAI-compatible endpoint can be added by pasting its base
  URL + model name (+ an optional key). Free tiers first, in the
  order you'd want them spent.
- On poor hardware the rings do the scaling: the tiny summarizer
  handles breadth, a small chat model handles basic use, and the
  reasoner is only spent on deep asks and the dwell beat. You do
  not need a big machine for basic use — see the Chromebook above.

**The WiCi brain** (Setup → Local brain → wici) is the split
option: the reasoner's expert work seesaws between the graphics
card and the processor, each holding its share, while cold
experts stream in from a fast SSD — the whole machine working,
not just one part. Chat stays whole on the graphics card (dense
work doesn't split), and the little summarizer rides the
processor so neither side sits idle. The split point is a
balance the plan computes from the two sides' speeds, and
leadership follows those speeds, never a fixed
graphics-card-first rule: on a many-core box with a small card
the processor leads the experts — the plan calls that
free-range inversion. On a box with an Nvidia card and an NVMe
drive the WiCi plan is real, and it prints its honest price up
front: an SSD feed bound (how fast the drive can stream
experts, under a stated cache assumption) and a patience cost —
the reasoner's tokens arrive slower than a card-only setup
would serve them; that's the trade, in numbers, before you
consent. On any other box the same plan prints as **FAUX**:
the split it *would* use, fully worked out, but nothing is
downloaded or run — the engine it names only works on Nvidia,
and the plan says so on its face.

## Pairing

**Pairing a daughter** (a second, smaller install that senses and
sends briefs home):

1. On the parent, open **Setup → Generate the daughter pairing
   secret**. It's shown once and saved to a local secrets file
   (owner-only permissions). Carry it to the daughter yourself.
2. On the daughter, set its role to **daughter** (Options → Role &
   daughters), give it the parent's host, and enter the same
   secret the same way.
3. From then on the daughter sends a small signed brief each
   dwell beat — floor state and a hash-linked receipt chain, no
   raw audio or video, ever. If the parent is off, briefs queue
   and drain when it returns.

**Pairing an agent over SSH** (at least one: Muse):

1. In **Setup**, paste the agent's public key. The app shows you
   its fingerprint — check it.
2. Press **Write the pairer script**. You get a small shell
   script. Carry it to the machine and run it there yourself.
   It installs the key restricted to the tailnet address range
   only (`from="100.64.0.0/10"`).
3. Nothing is trusted silently at any point — pairing is a
   button a person presses, with the fingerprint in front of
   them.

## Approvals, and the two limits

Whenever the app asks your approval — a setup step, a repair it
made to itself, a pairing — it shows two limits:

- the **declared** limit: what you're granting, in words;
- the **actual** limit: what this machine really measures
  (model size, memory it can honestly use, storage, speed).

If you want to push past a declared limit, you **provide power
and data**: a bigger local model, more hardware headroom, an API
tier, more storage. The app never just raises a number — and if
the declared and actual limits drift apart without anyone saying
so, the census files it as a gloss for your red pen.

Self-maintenance works the same way: mechanical repairs (a label,
an advertisement that names a tool wrong) are applied with a
backup and a receipt you can read; anything that changes behavior
is filed as a **proposal** and waits for you. It never runs
mid-conversation — only on the wake and dwell beats.

## Running it as an observer (no screen)

The app does not need its window. On a small machine — even a
small virtual machine — it can run **headless as an observer**:
just the eight little services, listening only to the machine
itself (loopback), with no screen and no client window.

Beside the services runs a tiny **snapshot loop**: once a minute
it writes one line to a log — the time, how busy the machine
is, how much memory is free, how many processes are alive,
whether each of the eight services answers, and how much memory
the services are using in total. That log is the observer's own
flowing floor of its host: a living baseline in a plain file,
which the app (and you) can read back over any window.

Why bother: the observer is a second set of eyes that never
sleeps. It keeps state about the machine it lives on while the
main app is closed, and it is one more angle in the room — when
a question comes up about how the box has been doing, the
observer's floor is a witness, not a guess.

Honest limits, stated up front:

- The footprint is small and measured: on a real run the eight
  services together used about **103 MB** of memory, and the
  snapshot loop about **12 MB** more.
- In this mode the services are plain processes, **not** system
  services (no systemd units). If the machine restarts, they
  stop. Nothing is lost but the watching — restart them by
  running the start script again.
- The doors (chat, Options, Setup, the Toy) are not available
  headless. The observer watches; it does not hold
  conversations.
- Everything lives in one **observer folder**: start and stop
  scripts, logs, pid files, and the snapshot log
  (`snapshots.jsonl`). Starting is idempotent — run the start
  script twice and it reports what is already running instead
  of doubling it.
- "Running" is a claim that gets verified, never assumed: each
  service must answer a real ping, and snapshot lines must
  actually land in the log, before the observer is called up.

## Your Joy Calculator profile

The Joy Calculator's 13 agree/disagree statements can be
answered **for you, from your own record** — with your
permission, and only with it. The idea: your answers already
exist, scattered through your data and your conversation
history. Answering from the record turns the calculator into
something that can answer questions about you — what depth you
chose, what you agreed to, where your limits are — without
asking you the same questions again.

The rules are strict, because the answers carry your name:

- **Every answer carries its source** — where in your record
  it came from — and a confidence mark: *Direct* (you said it)
  or *Practice* (it is your standing, documented way of
  operating).
- **What the record doesn't settle stays UNANSWERED.** Nobody
  invents a position in your name. An honest blank beats a
  confident guess.
- The profile keeps an explicit **cannot-answer list**: the
  questions this data does not support, written down as such.
- The result is a profile plus a question-and-answer sheet —
  and both are **yours**. They live on your machine only. The
  *method* is part of this app; the *profile* never leaves the
  house. Structure ships; house data never ships.

## How far it goes on its own: the three gradients

YOLO, but gradient-governed — the fun scales with the proof,
not instead of it. Three gradients set how much latitude the
system takes on work like the observer and the profile above:

- **Confidence**: latitude grows as measured agreement hardens
  (pings answered, snapshots landing, checks agreeing), and
  shrinks the moment agreement does.
- **Comfort**: privilege climbs in announced steps. Deeper
  access is offered, never taken — the owner's tap is the gate.
- **Patience**: things are allowed to form at their own rate.
  A baseline that takes an hour to earn is worth more than one
  forced in a minute.

Within those three, the instruction is generous: take the most
fun the gradients can honestly offer.

## The calm rules

- The main screen stays calm: relationship, floor state, who's
  serving. Everything else is behind a door you open on purpose.
- Explainers wait for a dwell before they speak. They're manners,
  not popups.
- The Eddy Toy tab is a toy. It is the one room with no harness:
  no score, no records, nothing learned about you. Poke the pond.
