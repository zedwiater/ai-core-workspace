# Repairs glossary — commands for repairs

Every failure this app has actually had in the field, what caused
it (proven) or may have caused it (suspected, and labeled as
such), the repair commands, and the prevention now built in.
Written to be executed verbatim — by a human at a keyboard, by a
shell, or by an AI (small, MoE, big, open — the commands are
complete, ordered, and state what success looks like).

Conventions: run user commands as your normal user; `sudo` where
shown. The app checkout is assumed at `~/ai-core-workspace`.

## Universal rescue (the app is stuck, stacked, or eating the machine)

Works without a working desktop. Switch to a text console:

1. `Ctrl+Alt+F3`, log in as your normal user.
2. `pkill -f ai-client.py`
3. `rm -f ~/.config/autostart/ai-core.desktop`
4. `Ctrl+Alt+F1` (or F2) back to the desktop.

Then, at leisure: `ai-core-report` to capture the failure, and
`sudo bash install.sh uninstall` (from the checkout) to remove.

## R1 — The model popup ignores every click

**Symptom:** "Your models, your call" renders, buttons do nothing,
the dialog never closes (it has no close button of its own).
**Cause (proven, 2026-11-17):** PyGObject invokes async callbacks
as `(source, result, user_data)`; the handler was written for two
arguments and died on every click.
**Repair:** update (`bash update.sh`); the advice also waits on
the Conduit page — the popup is advisory only. To silence it on
any build that has the plain-language switches:
`printf '{"options": {"model_advice_popup": false}}' > ~/.config/ai-core/conduit.json`
**Prevention:** the handler accepts both arities; a source test
pins the signature.

## R2 — The client crashes seconds after opening (Vulkan)

**Symptom:** a good first frame, then
`VK_ERROR_TOO_MANY_OBJECTS` / `vkCreateSwapchainKHR` warnings and
a segfault.
**Cause (proven class):** GTK 4's Vulkan renderer exhausting
swapchain objects on Intel/Mesa graphics stacks.
**Repair:** `GSK_RENDERER=gl ai-client`; deeper fallback:
`GSK_RENDERER=cairo ai-client`.
**Prevention:** current builds default to the GL renderer before
any window exists (an owner's own `GSK_RENDERER` still wins).

## R3 — Copies of the app stack up; it persists across reboots

**Symptom:** multiple instances accumulate until the machine
chokes; the app returns after every reboot, uninvited.
**Cause (established by audit):** no self-relaunch exists in the
client; the stacking lived in the launch paths — an
installer-written autostart entry, desktop session restore, and
manual launches — landing on a crash-prone build, with no
instance guard.
**Repair:** the universal rescue above, then update.
**Prevention:** the client takes a non-blocking file lock
(`~/.cache/ai-core/client.lock`) — a second launch, whoever sent
it, prints and leaves; re-activation only raises the one window;
the installer no longer writes an autostart entry (opt-in:
`cp /usr/share/applications/ai-core.desktop ~/.config/autostart/`).

## R4 — The kernel terminates the app ("Memory Shortage Avoided")

**Symptom:** a kernel/desktop notification that AI Core Workspace
was terminated because the system is low on memory; before that,
the machine "locks up" (it is thrashing, not dead).
**Cause (proven in effect, 2026-11-17):** stacked instances (R3)
plus, on small machines, a model seated too large and kept
resident forever. Do NOT press the notification's "Restart
Application" — it relaunches the same build.
**Repair:** universal rescue; remove; reinstall current.
**Prevention:** the pairing reserves 2 GB for the OS/desktop
before seating a model (7 GB pairs the 3B class, not the 8B);
under 12 GB RAM the service shape is one seat with a 5-minute
idle unload instead of resident-forever.

## R5 — The installer declares success with no model door

**Symptom:** "installed successfully" but the app can't reach any
model; `ollama` may not exist at all.
**Cause (proven):** a single-shot API check raced the service
start, and a dead door fell into the same branch as an empty
shelf, so the run sailed on.
**Repair:** `journalctl -u ollama -n 20` shows the door's own
story; `sudo systemctl enable --now ollama`; re-run the
installer (re-running is safe by design).
**Prevention:** the installer waits up to 30 s for the door,
counts it in validation, prints INCOMPLETE and exits non-zero
when it never answers.

## R6 — Ollama's own install fails ("a terminal is required")

**Symptom:** during Step 4, `sudo: a terminal is required to read
the password`, then `Unit ollama.service not found`.
**Cause (proven):** the upstream installer was run as the user;
its internal sudo calls had no TTY.
**Repair:** update — current builds run the upstream installer
as root, which is what it expects.
**Prevention:** that, plus R5's door verdict catching any
recurrence loudly.

## R7 — The install is the OLD app (stale checkout / wrong branch)

**Symptom:** the UI is unchanged after "updating"; new steps
(pairing, merge) never appear in the install log.
**Cause (proven):** `git pull` only moves the branch you are
standing on, and a failed `git clone` leaves a stale tree in
place silently. For a day, this repo's own updates landed on a
working branch while the default branch (what a plain clone
gets) held the old app.
**Check:** `cd ~/ai-core-workspace && git log --oneline -1` —
compare with the newest commit on the repo's front page. The
installer's first line also names its build ("conduit build");
anything else is stale.
**Repair (cannot lie):** `cd ~ && rm -rf ai-core-workspace &&
git clone https://github.com/zedwiater/ai-core-workspace.git`,
verify the log line, then `bash install.sh`.
**Prevention:** the app lives on the default branch; the build
banner; `get.sh`/`update.sh` track the default branch.

## R8 — The uninstaller crashes ("REAL_HOME: unbound variable")

**Symptom:** `install.sh uninstall` dies at line ~32 before
removing anything.
**Cause (proven):** the uninstall block spends `$REAL_HOME`
before the script computed it, under `set -u`.
**Repair (works on the broken build):**
`sudo REAL_HOME=/home/<your-user> bash install.sh uninstall`
**Prevention:** the definitions now sit above every mode; a
source-order test pins them there.

## R9 — The machine drops to an emergency shell at boot

**Symptom:** boot stops at "You are in emergency mode" after
repeated hard power-offs (for example, after R4 events).
**Possible causes (suspected, general Linux):** a filesystem
check demanding its turn, or a mount that failed/timed out.
**Guidance:** do not keep power-cycling. Let a boot complete —
a check often finishes on the next attempt. If it recurs,
photograph the emergency screen (it names the failing unit) and
work from that; from the shell, `journalctl -xb` tells the story.
This is an OS-level event, not an app state: remove the app from
a TTY (universal rescue) only after the machine boots stably.

## R11 — The window has no titlebar: can't move it, no X to close it, sizing is weird

**Symptom.** The app opens but there is nothing to drag and no
close button; the window size looks wrong.

**Cause (proven from the source).** The client set the notebook
as the window's content and never built a header bar. GTK 4 on
Wayland draws no server-side decorations to fall back on, so
the window had no drag surface and no controls. The sizing
half: a non-scrollable thirteen-tab notebook and pages that
propagate their natural size forced a minimum the window then
had to wear.

**Repair.** Update — the window now carries a real header bar
(title, window controls, drag surface) via a toolbar view,
the notebook scrolls its tabs, and the pages no longer force
their natural size onto the window:

```
cd ~/ai-core-workspace && git pull && bash update.sh
```

**Prevention.** The chrome is pinned by tests
(`tests/test_window_chrome.py`): the header-bar construction
and the sizing guards must be present in the source.

## Reporting any failure

`ai-core-report` builds one redacted file
(`~/ai-core-failure-report.md`: machine shape, service and door
states, journal tails — home path, username, hostname stripped)
and prints a prefilled GitHub issue link. Nothing is sent
automatically; the human reviews and submits. An AI asked to
"report it" should run the command, show the file, and stop
there — sending is the owner's act.

## R10 — Chat fails, ollama ps is empty, the CLI answers EOF

**Symptom:** chat errors on every model; `ollama run <model>`
answers EOF; `ollama ps` shows nothing loaded although the app
lists models.
**Cause (proven, 2026-11-17):** the app never seated anything —
a shelf listing is not a seat — and the first chat tried to load
an 8B (5.2 GB weights) into a 7.6 GB machine with 3.1 GB free
and no swap. The kernel OOM-killed the ollama SERVICE
(`systemctl status ollama` / journal: "Failed with result
'oom-kill'"), and every client of the dead door saw EOF.
**Check:** `journalctl -u ollama -n 30` for 'oom-kill';
`free -h` for the arithmetic (weights x 1.3 must fit the FREE
memory, not the total).
**Repair:** pull the model the pairing chose for the hardware
(`ollama pull qwen2.5:3b` on a 7 GB machine) and select it.
**Prevention:** selecting a model in the app now seats it —
load call, then proof via /api/ps in the header — and a seat
that cannot fit the free memory is refused with the arithmetic
shown, before the kernel has to refuse it harder.
