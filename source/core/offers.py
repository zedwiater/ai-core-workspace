# --- AI Core module label ---
# Label-Name: offers
# Label-Origin: ai-core-workspace build (Zak/Muse)
# Label-Version: 1
# Label-Does: detects what only the user can fix or link, and
#   offers the exact commands — the app prescribes, the user
#   runs, the app re-checks
# --- end label ---
"""The command-offering layer (Zak, 2026-11-18).

Diagnosis without prescription strands people: the app could
report 'ffmpeg failed' all night while the actual fix — one
sudo command — sat in a human's head. This module closes that
loop for the failures we have really met:

- ffmpeg missing, or present-but-broken (the Arch partial-
  upgrade soname mismatch that silenced a laptop's senses)
- docker present but the user is not in its group, or the
  daemon is down
- a camera device exists but the user cannot open it
  (the video group)
- the model service (Ollama) is not answering

Each offer is plain data: a title, a one-line why, the exact
commands, and the name of a check. detect() probes the
machine and returns only the offers that apply; run_check()
re-probes after the user has run a command, so the app —
not the user's guess — says whether it worked. The user's
sudo stays the user's: nothing here runs a command.
"""
import glob as glob_mod
import os
import shutil
import subprocess
import urllib.request

# Every offer and every library entry carries this. The app
# prescribes; it never runs a command itself, and the user
# can — should — verify any command before trusting it.
DISCLAIMER = (
    "The app never runs these commands — they are yours to "
    "run, in your own terminal, with your own password. "
    "Before you run one, double-check it online: search the "
    "command together with your system (for example "
    "'pacman -Syu arch wiki'), and if what you read does "
    "not match the explanation here, do not run it.")


def distro_family(which=shutil.which):
    if which("pacman"):
        return "arch"
    if which("apt"):
        return "debian"
    return "other"


def _run(cmd, timeout=4, runner=subprocess.run):
    try:
        r = runner(cmd, capture_output=True, text=True,
                   timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return None, str(e)


# ---------------------------------------------------------- probes
# Each returns a state word; "ok"/"absent" need no human hands.

def ffmpeg_state(runner=subprocess.run, which=shutil.which):
    if not which("ffmpeg"):
        return "missing"
    rc, _out = _run(["ffmpeg", "-version"], timeout=4,
                    runner=runner)
    return "ok" if rc == 0 else "broken"


def docker_state(runner=subprocess.run, which=shutil.which):
    if not which("docker"):
        return "absent"
    rc, out = _run(["docker", "ps"], timeout=4, runner=runner)
    if rc == 0:
        return "ok"
    if "permission denied" in out.lower():
        return "denied"
    return "down"


def video_state(globber=glob_mod.glob, access=os.access):
    devices = sorted(globber("/dev/video*"))
    if not devices:
        return "absent"
    for dev in devices:
        if access(dev, os.R_OK | os.W_OK):
            return "ok"
    return "denied"


def ollama_state(opener=urllib.request.urlopen):
    try:
        with opener("http://127.0.0.1:11434/api/tags",
                    timeout=2) as resp:
            return "ok" if resp.status == 200 else "down"
    except Exception:
        return "down"


CHECKS = {
    "ffmpeg_ok": lambda **kw: ffmpeg_state(**kw) == "ok",
    "docker_ok": lambda **kw: docker_state(**kw)
    in ("ok", "absent"),
    "video_ok": lambda **kw: video_state(**kw)
    in ("ok", "absent"),
    "ollama_ok": lambda **kw: ollama_state(**kw) == "ok",
    "update_ok": lambda **kw: _update_state().get("state")
    == "current",
}


# ---------------------------------------------------- the library
# The standing reference, built from the commands a user of
# this app has actually had to be handed (Zak's history,
# 2026-11-17/18): every one was a moment where the app
# stopped and a human needed the exact words. Each entry
# says WHEN it applies — the library is browsable any time,
# detected offers are the urgent subset.

def library(src=None):
    if src is None:
        src = _update_state().get("src") or "~/ai-core-workspace"
    return [
        {"id": "repair-update",
         "title": "A program suddenly can't start after "
                  "some updates",
         "when": "ffmpeg (or anything) reports a missing or "
                 "mismatched library after a partial update",
         "commands": ["sudo pacman -Syu"],
         "explainer": "On Arch-family systems a partial "
                      "update can leave a program and its "
                      "libraries at different versions. -Syu "
                      "updates everything together so they "
                      "match again. (Debian family: sudo apt "
                      "update && sudo apt upgrade.)"},
        {"id": "manual-update",
         "title": "Update the app from the terminal",
         "when": "an update is waiting and you'd rather run "
                 "it yourself than use the header button",
         "commands": ["sudo ai-core-update"],
         "explainer": "Pulls the newest app code and "
                      "re-installs. Models, other setups' "
                      "service settings, and your app "
                      "settings are all left alone by design."},
        {"id": "manual-refresh",
         "title": "Refresh the app's source checkout",
         "when": "you want the newest code in the checkout "
                 "the app was installed from",
         "commands": [f"cd {src} && git pull"],
         "explainer": "git pull downloads the newest "
                      "commits into the local copy. It "
                      "changes only source files; the daily "
                      "timer or ai-core-update does the "
                      "actual installing."},
        {"id": "auto-update-off",
         "title": "Stop the app updating itself daily",
         "when": "you'd rather update by hand, always",
         "commands": ["sudo systemctl disable --now "
                      "ai-core-update.timer"],
         "explainer": "Disables and stops the daily update "
                      "timer. The app keeps working; updates "
                      "become your job (see manual update). "
                      "Re-enable with enable --now instead "
                      "of disable."},
        {"id": "merge-escape",
         "title": "The installer 'merged' and the app can't "
                  "shape its model service",
         "when": "the installer said MERGE MODE because "
                 "Ollama settings from another setup exist, "
                 "and the app's model won't seat — AND those "
                 "settings are yours to retire",
         "commands": [
             "sudo cp /etc/systemd/system/ollama.service.d/"
             "override.conf ~/ollama-override-backup.conf",
             "sudo rm /etc/systemd/system/ollama.service.d/"
             "override.conf",
             "sudo systemctl daemon-reload",
             "sudo systemctl restart ollama"],
         "explainer": "The FIRST command backs the file up "
                      "to your home folder — nothing is "
                      "lost. The rest remove the other "
                      "setup's Ollama tuning, let the system "
                      "notice, and restart the service, so "
                      "the app's next install can write its "
                      "own shape. Only do this if that "
                      "tuning is truly retired — another "
                      "tool may depend on it."},
        {"id": "make-report",
         "title": "Make a failure report to share",
         "when": "something is broken and you want help "
                 "with receipts attached",
         "commands": ["ai-core-report"],
         "explainer": "Builds one report file at "
                      "~/ai-core-failure-report.md with "
                      "private details redacted BEFORE "
                      "writing, plus a ready GitHub issue "
                      "link. Nothing is sent anywhere unless "
                      "you send it."},
    ]


def library_text(src=None):
    """The library as plain text for the Help page."""
    lines = ["— Commands you might need —", "",
             "Exact commands for the moments the app needs "
             "your hands. " + DISCLAIMER, ""]
    for entry in library(src):
        lines.append(entry["title"])
        lines.append(f"When: {entry['when']}")
        for cmd in entry["commands"]:
            lines.append(f"  {cmd}")
        lines.append(entry["explainer"])
        lines.append("")
    return "\n".join(lines)


def run_check(check_id, **kw):
    """Re-probe one offer's condition. True = resolved."""
    fn = CHECKS.get(check_id)
    if fn is None:
        return False
    try:
        return bool(fn(**kw))
    except Exception:
        return False


# ---------------------------------------------------------- offers

def _ffmpeg_commands(state, family):
    if state == "missing":
        if family == "arch":
            return ["sudo pacman -S ffmpeg"]
        if family == "debian":
            return ["sudo apt update && sudo apt install -y ffmpeg"]
        return ["# install ffmpeg with your system's "
                "package manager"]
    # broken: present but cannot run — a half-updated library
    # world underneath it (the 2026-11-18 laptop case)
    if family == "arch":
        return ["sudo pacman -Syu"]
    if family == "debian":
        return ["sudo apt install --reinstall -y ffmpeg"]
    return ["# reinstall ffmpeg with your system's "
            "package manager"]


def _update_state():
    """The app-update check, reused: behind/current/unknown."""
    try:
        from core import update_check
        return update_check.check()
    except Exception:
        return {"state": "unknown"}


def detect(runner=subprocess.run, which=shutil.which,
           globber=glob_mod.glob, access=os.access,
           opener=urllib.request.urlopen,
           update_probe=None):
    """Probe the machine; return the offers that apply —
    each a dict: id, title, why, commands, explainer,
    disclaimer, check, reach. Every command is grounded in
    what the crawl finds on THIS machine: no docker here,
    no docker offer."""
    family = distro_family(which)
    offers = []

    fstate = ffmpeg_state(runner, which)
    if fstate in ("missing", "broken"):
        offers.append({
            "id": "ffmpeg",
            "title": "The camera and microphone tools need "
                     "ffmpeg working",
            "why": ("ffmpeg is not installed, so the senses "
                    "have no hands." if fstate == "missing"
                    else "ffmpeg is installed but cannot start "
                         "— usually a half-finished system "
                         "update left its libraries mismatched. "
                         "A full update is the repair."),
            "commands": _ffmpeg_commands(fstate, family),
            "explainer": (
                "pacman -Syu (Arch) brings every system "
                "package up to date together, so programs and "
                "their libraries match again — the usual cause "
                "of 'cannot start' after a partial update. "
                "apt's reinstall (Debian) fetches a clean copy "
                "of ffmpeg and its files. Either can take a "
                "few minutes and may ask you to restart."),
            "disclaimer": DISCLAIMER,
            "check": "ffmpeg_ok",
            "reach": None,
        })

    dstate = docker_state(runner, which)
    if dstate == "denied":
        offers.append({
            "id": "docker-group",
            "title": "Docker is here but won't talk to your "
                     "account yet",
            "why": "Your user is not in the docker group. "
                   "Run this, then log out and back in.",
            "commands": ["sudo usermod -aG docker $USER"],
            "explainer": (
                "usermod -aG adds your account to the docker "
                "group — the group Docker listens to — without "
                "removing any group you already have. Group "
                "changes only apply at login, which is why "
                "the log-out step matters."),
            "disclaimer": DISCLAIMER,
            "check": "docker_ok",
            "reach": "docker",
        })
    elif dstate == "down":
        offers.append({
            "id": "docker-down",
            "title": "Docker is installed but its service "
                     "is not running",
            "why": "The app can link to Docker once the "
                   "daemon is up.",
            "commands": ["sudo systemctl start docker"],
            "explainer": (
                "systemctl start asks the system to run "
                "Docker's background service now. It does not "
                "change any container or image; it just "
                "starts the engine."),
            "disclaimer": DISCLAIMER,
            "check": "docker_ok",
            "reach": "docker",
        })

    if video_state(globber, access) == "denied":
        offers.append({
            "id": "video-group",
            "title": "A camera is plugged in but your account "
                     "can't open it",
            "why": "The device belongs to the video group. "
                   "Run this, then log out and back in.",
            "commands": ["sudo usermod -aG video $USER"],
            "explainer": (
                "usermod -aG adds your account to the video "
                "group, which owns camera devices on most "
                "Linux systems. Nothing else changes; the "
                "membership applies from your next login."),
            "disclaimer": DISCLAIMER,
            "check": "video_ok",
            "reach": "cameras",
        })

    if ollama_state(opener) == "down":
        offers.append({
            "id": "ollama-down",
            "title": "The model service (Ollama) is not "
                     "answering",
            "why": "Chat and seating need it. Restarting it "
                   "does not remove any models. If this "
                   "machine's models are managed by another "
                   "setup, use that setup's way instead.",
            "commands": ["systemctl status ollama",
                         "sudo systemctl restart ollama"],
            "explainer": (
                "The first command only LOOKS — it shows "
                "whether the service is stopped or crashed, "
                "and why. The second restarts the service; "
                "models on disk are untouched, though a model "
                "currently loaded in memory will need to load "
                "again on its next use."),
            "disclaimer": DISCLAIMER,
            "check": "ollama_ok",
            "reach": None,
        })

    ustate = (update_probe or _update_state)()
    if ustate.get("state") == "behind":
        offers.append({
            "id": "app-update",
            "title": f"An app update is waiting "
                     f"({ustate.get('behind')} new)",
            "why": "The header button can run it too — this "
                   "is the same update from the terminal.",
            "commands": ["sudo ai-core-update"],
            "explainer": (
                "ai-core-update pulls the newest app code "
                "and re-runs the installer, which is careful "
                "by design: it never removes your models, "
                "never overwrites another setup's service "
                "settings, and leaves your app settings "
                "alone."),
            "disclaimer": DISCLAIMER,
            "check": "update_ok",
            "reach": None,
        })

    return offers


def for_reach(offers, reach_id):
    """The offer (if any) that belongs to a Nodes reach row."""
    for offer in offers or []:
        if offer.get("reach") == reach_id:
            return offer
    return None
