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

## The calm rules

- The main screen stays calm: relationship, floor state, who's
  serving. Everything else is behind a door you open on purpose.
- Explainers wait for a dwell before they speak. They're manners,
  not popups.
- The Eddy Toy tab is a toy. It is the one room with no harness:
  no score, no records, nothing learned about you. Poke the pond.
