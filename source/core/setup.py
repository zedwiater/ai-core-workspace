"""Setup — the first-run thread: look, announce, consent, thread.

This module is the plan engine behind the Setup door. It splits
into two halves with a hard line between them:

  READ-ONLY half: detect_profile() inspects a fresh Linux box
  (distro/package manager, cores, RAM, GPU, disk, home) and never
  changes anything. build_plan() is a PURE function over a profile
  dict + the owner's choices — every step is data: title, why, the
  EXACT commands, privilege floor, network/disk/time costs.
  render_script() turns a plan into the dry-run script — what you
  read is what would run.

  EXECUTION half: deliberately not here. The Setup door in the
  client runs steps one at a time, with receipts, behind explicit
  button presses on the privilege comfort gradient:

    level 0  look only
    level 1  user-space changes only
    level 2  ask me per sudo step (exact command shown first)
    level 3  standing grant for this setup session only

  No silent sudo exists anywhere in the design: a step that needs
  sudo carries min_level 2 and is HELD — visible, costed, and
  skipped — below it.

Transparent cost, up front: build_plan totals disk, downloads,
minutes, and money ("$0 by default") before anything runs. The
HOME FOLDER MINIMUM mode keeps every artifact under ~/ai-core —
user-space brain (Ollama tarball), user systemd units — and says
plainly that the only system footprint left is whatever GTK
packages the box already has or the owner consents to add.

Model sizing improves on install.sh's memory-only rule: it reads
cores + RAM + GPU VRAM when detectable, and every recommendation
carries its reasoning line, labeled an estimate.

Secrets (API keys, chat-door tokens, the pairing secret) live in
~/.config/ai-core/secrets.json at mode 0600 — written by
save_secret(), never logged, never required.
"""
import base64
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path

from core.protocol import SERVICE_PORTS

# --- Read-only inspection ----------------------------------------------

_PKG_BY_ID = {
    "debian": "apt", "ubuntu": "apt", "linuxmint": "apt",
    "pop": "apt", "raspbian": "apt",
    "fedora": "dnf", "rhel": "dnf", "centos": "dnf",
    "arch": "pacman", "manjaro": "pacman", "endeavouros": "pacman",
}

_DEPS = {
    "apt": "sudo apt-get install -y python3-gi gir1.2-gtk-4.0 "
           "gir1.2-adw-1 ffmpeg",
    "dnf": "sudo dnf install -y python3-gobject gtk4 libadwaita ffmpeg",
    "pacman": "sudo pacman -S --needed --noconfirm python-gobject "
              "gtk4 libadwaita ffmpeg",
}


def detect_profile():
    """Look at the box. Read-only; every probe is guarded, and a
    probe that can't run just leaves its field unknown."""
    prof = {
        "os_id": "unknown", "pkg_mgr": None,
        "cores": os.cpu_count() or 1, "ram_gb": 0.0,
        "gpu": None, "disk_free_gb": 0.0,
        "home": str(Path.home()), "arch": platform.machine(),
    }
    try:
        fields = {}
        for line in Path("/etc/os-release").read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                fields[k] = v.strip('"')
        prof["os_id"] = fields.get("ID", "unknown")
        like = fields.get("ID_LIKE", "")
        prof["pkg_mgr"] = _PKG_BY_ID.get(prof["os_id"]) or next(
            (_PKG_BY_ID[t] for t in like.split() if t in _PKG_BY_ID),
            None)
    except Exception:
        pass
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                prof["ram_gb"] = round(
                    int(line.split()[1]) / 1024 / 1024, 1)
                break
    except Exception:
        pass
    try:
        prof["disk_free_gb"] = round(
            shutil.disk_usage(prof["home"]).free / 1e9, 1)
    except Exception:
        pass
    prof["gpu"] = _probe_gpu()
    return prof


def _probe_gpu():
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=4)
        if out.returncode == 0 and out.stdout.strip():
            name, mem = out.stdout.strip().splitlines()[0].split(",")
            m = re.search(r"(\d+)", mem)
            return {"vendor": "nvidia", "name": name.strip(),
                    "vram_gb": round(int(m.group(1)) / 1024, 1)
                    if m else None}
    except Exception:
        pass
    try:
        out = subprocess.run(["lspci"], capture_output=True, text=True,
                             timeout=4)
        for line in out.stdout.splitlines():
            if "VGA compatible controller" in line or "3D controller" in line:
                low = line.lower()
                vendor = ("nvidia" if "nvidia" in low else
                          "amd" if ("amd" in low or "ati" in low) else
                          "intel" if "intel" in low else "unknown")
                return {"vendor": vendor,
                        "name": line.split(":", 2)[-1].strip(),
                        "vram_gb": None}
    except Exception:
        pass
    return None


# --- Model sizing --------------------------------------------------------

# (min usable GB, chat, reason, summarizer) — sizes are download
# estimates in GB for the named Ollama weights; 0.0 = shares the
# weights of another slot (counted once).
_TIERS = [
    (38.0, ("qwen2.5:32b", 19.0), ("qwen2.5:32b", 0.0),
     ("gemma3:4b", 3.3)),
    (18.0, ("qwen2.5:14b", 9.0), ("qwen2.5:32b", 19.0),
     ("gemma3:4b", 3.3)),
    (9.0, ("qwen2.5:7b", 4.7), ("qwen2.5:14b", 9.0),
     ("qwen2.5:3b", 1.9)),
    (4.5, ("qwen2.5:3b", 1.9), ("qwen2.5:7b", 4.7),
     ("gemma3:1b", 0.8)),
    (0.0, ("gemma3:1b", 0.8), ("gemma3:1b", 0.0),
     ("gemma3:1b", 0.0)),
]


def usable_gb(profile):
    """What a model may honestly occupy: VRAM when a real GPU
    reports it, else a working share of system RAM."""
    gpu = profile.get("gpu") or {}
    if gpu.get("vram_gb"):
        return float(gpu["vram_gb"]), "VRAM"
    return round(float(profile.get("ram_gb", 0)) * 0.6, 1), "RAM"


def _tier_row(usable):
    """The sizing row a usable-GB figure lands on."""
    for row in _TIERS:
        if usable >= row[0]:
            return row
    return _TIERS[-1]


# True download size per model — a 0.0 in _TIERS means "shares
# another slot's weights", never that the weights weigh nothing.
_MODEL_SIZE_GB = {}
for _row in _TIERS:
    for _model, _size in _row[1:]:
        _MODEL_SIZE_GB[_model] = max(
            _size, _MODEL_SIZE_GB.get(_model, 0.0))

# Reason-slot candidates, largest first — the ladder the WiCi
# residency caps step down.
_REASON_LADDER = sorted(
    {row[2][0]: _MODEL_SIZE_GB[row[2][0]] for row in _TIERS}.items(),
    key=lambda kv: -kv[1])


# --- WiCi sizing (brain "wici") --------------------------------------
#
# The WiCi pattern (WiCi One / InferSSD — WiCi's open-source
# llama.cpp fork, Apache-2.0; cross-ref filed 2026-10-30): the
# dense path stays resident on the GPU leg, MoE expert work
# seesaws between the GPU and CPU legs running concurrently, and
# cold experts stream from SSD — a third leg that can bind below
# both processors. In this app only the REASON slot is treated
# as MoE-shaped, so only it is sized and split this way; chat
# keeps the dense sizing (the 2026-11-13 faux-split run, finding
# C: dense work does not seesaw). The whole system still works:
# the summarizer is assigned to the CPU leg, so no leg idles
# while the other processes — the system wants the whole system
# to function, not just select parts.
#
# The rate model is ASSUMED — declared here, printed on the
# plan's face, and replaced by measurement on any box that
# actually runs the split:
WICI_GPU_EXPERT_RATE = 100.0          # ASSUMED GPU expert-leg rate
WICI_CPU_EXPERT_RATE_PER_CORE = 6.25  # ASSUMED CPU rate per core
WICI_CACHE_HIT = 0.85                 # ASSUMED expert-cache locality
WICI_DRIVE_GB_S = 7.0                 # ASSUMED NVMe stream (GB/s)


def wici_cpu_rate(cores):
    """The CPU expert leg's ASSUMED rate on this box."""
    return WICI_CPU_EXPERT_RATE_PER_CORE * max(1, int(cores or 1))


def wici_fulcrum(cpu_rate, gpu_rate):
    """beta* = Rc/(Rc+Rg): the share of expert work the CPU leg
    carries when both legs finish together. Leadership follows
    the rates — beta* above 0.5 means the CPU leg leads the
    experts (free-range inversion), never a fixed GPU-first
    rule."""
    return cpu_rate / (cpu_rate + gpu_rate)


def _wici_pools(profile):
    """(combined usable GB, VRAM GB, usable RAM GB). The WiCi
    reasoner is sized against VRAM + usable RAM together,
    because its experts live on both legs."""
    gpu = profile.get("gpu") or {}
    vram = float(gpu.get("vram_gb") or 0.0)
    usable_ram = round(float(profile.get("ram_gb", 0) or 0) * 0.6, 1)
    return round(vram + usable_ram, 1), vram, usable_ram


def wici_reason_pick(profile):
    """(model, footprint GB) for the WiCi reason slot: the tier
    the COMBINED pool buys, stepped down the reason ladder until
    each leg can actually hold its fulcrum share (GPU share ≤
    VRAM, CPU share ≤ usable RAM, where those are known)."""
    combined, vram, usable_ram = _wici_pools(profile)
    beta = wici_fulcrum(wici_cpu_rate(profile.get("cores", 1)),
                        WICI_GPU_EXPERT_RATE)
    model = _tier_row(combined)[2][0]
    footprint = _MODEL_SIZE_GB[model]
    caps = []
    if vram > 0:
        caps.append(vram / (1.0 - beta))
    if usable_ram > 0:
        caps.append(usable_ram / beta)
    cap = min(caps) if caps else float("inf")
    for cand, size in _REASON_LADDER:
        if size <= footprint and size <= cap:
            return cand, size
    return _REASON_LADDER[-1]


def wici_details(profile, reason_model):
    """plan["wici"]: the fulcrum split, the per-slot leg
    assignments, the SSD feed bound, and the patience cost, for
    one box and one reasoner. FAUX whenever the box has no
    Nvidia GPU — the engine is CUDA-only, so on any other box
    the plan is the split it WOULD use, and says so. Every rate
    in it is ASSUMED and labeled."""
    gpu = profile.get("gpu") or {}
    faux = gpu.get("vendor") != "nvidia"
    footprint = _MODEL_SIZE_GB[reason_model]
    cores = profile.get("cores", 1)
    rc = wici_cpu_rate(cores)
    beta = wici_fulcrum(rc, WICI_GPU_EXPERT_RATE)
    cpu_gb = round(beta * footprint, 2)
    gpu_gb = round(footprint - cpu_gb, 2)
    streamed = round(footprint * (1.0 - WICI_CACHE_HIT), 3)
    bound = round(WICI_DRIVE_GB_S / streamed, 2) if streamed \
        else None
    # Patience cost, from the same ASSUMED model. Bridging
    # assumption, declared: one unit of expert work = 1 GB of
    # expert weights touched, rates read as GB/s-equivalents.
    # A resident all-GPU path pays footprint/Rg per token; the
    # split pays max(fulcrum compute, SSD feed) — and the feed
    # is usually the long pole. That gap is the patience.
    t_all_gpu = footprint / WICI_GPU_EXPERT_RATE
    t_split = max(footprint / (rc + WICI_GPU_EXPERT_RATE),
                  streamed / WICI_DRIVE_GB_S)
    delta = round((t_split - t_all_gpu) / t_all_gpu * 100, 1)
    if delta >= 0:
        patience_note = (
            f"Throughput bought with patience: the split runs "
            f"a reasoner this box could not hold on the GPU "
            f"alone, and at the fulcrum its tokens arrive "
            f"~{delta:g}% slower than a resident all-GPU path "
            f"would serve them — the SSD feed, not either "
            f"processor, sets the pace.")
    else:
        patience_note = (
            f"Throughput bought with patience: at this size "
            f"the feed leg does not bind, so the fulcrum split "
            f"runs ~{abs(delta):g}% quicker per token than the "
            f"all-GPU path — the patience is spent only when "
            f"the reasoner outgrows the drive's feed.")
    lead = "cpu" if beta > 0.5 else "gpu"
    if faux:
        legs = [
            {"slot": "chat", "legs": ["cpu"],
             "note": "FAUX — no Nvidia on this box, so the "
                     "dense path rides the CPU leg here; on an "
                     "Nvidia box it is GPU-leg primary, "
                     "unsplit"},
            {"slot": "reason", "legs": ["cpu"],
             "note": f"FAUX — no split runs here; the split it "
                     f"WOULD use: beta* {round(beta, 3)} across "
                     f"GPU+CPU legs ({gpu_gb} GB GPU / "
                     f"{cpu_gb} GB CPU)"},
            {"slot": "summarizer", "legs": ["cpu"],
             "note": "CPU leg — its assignment in both modes"},
        ]
    else:
        legs = [
            {"slot": "chat", "legs": ["gpu"],
             "note": "dense path — GPU-leg primary, unsplit: "
                     "dense work does not seesaw (faux-split "
                     "finding C)"},
            {"slot": "reason", "legs": ["gpu", "cpu"],
             "note": f"MoE seesaw at the fulcrum beta* "
                     f"{round(beta, 3)}: ~{gpu_gb} GB of "
                     f"experts on the GPU leg, ~{cpu_gb} GB on "
                     f"the CPU leg"
                     + (" — free-range inversion: the CPU leg "
                        "leads the experts on this box"
                        if lead == "cpu" else "")},
            {"slot": "summarizer", "legs": ["cpu"],
             "note": "CPU leg by default — tiny and "
                     "latency-tolerant, so no leg idles while "
                     "the other works"},
        ]
    return {
        "faux": faux,
        "beta": round(beta, 3),
        "lead_leg": lead,
        "gpu_gb": gpu_gb, "cpu_gb": cpu_gb,
        "reason_gb": footprint,
        "rate_basis": (
            f"ASSUMED rates: GPU expert leg "
            f"{WICI_GPU_EXPERT_RATE:g} units; CPU expert leg "
            f"{WICI_CPU_EXPERT_RATE_PER_CORE:g} units/core × "
            f"{cores} cores = {rc:g} units; beta* = Rc/(Rc+Rg). "
            "Estimates until measured on the box."),
        "legs": legs,
        "feed": {
            "streamed_gb_per_token": streamed,
            "cache_hit": WICI_CACHE_HIT,
            "cache_hit_basis": "ASSUMED expert-cache locality",
            "drive_gb_s": WICI_DRIVE_GB_S,
            "drive_basis": "ASSUMED NVMe-class stream rate",
            "bound_tok_s": bound,
        },
        "patience_cost": {
            "est_latency_delta_pct": delta,
            "basis": "ASSUMED rate model + SSD feed leg; "
                     "bridging assumption: 1 unit of expert "
                     "work = 1 GB of expert weights touched, "
                     "rates read as GB/s-equivalents",
            "note": patience_note,
        },
    }


def recommend_models(profile, brain=None):
    """Per-slot model picks with the reasoning shown. Estimates,
    labeled as such — measured tok/s replaces them after install.
    brain="wici" re-sizes the REASON slot only, against the
    combined VRAM+RAM pool (see the WiCi block above); every
    other brain — and the default — is today's behavior,
    unchanged."""
    usable, basis = usable_gb(profile)
    _floor_gb, chat, reason, summ = _tier_row(usable)
    gpu = profile.get("gpu") or {}
    where = (f"{gpu.get('name', 'GPU')} with {gpu['vram_gb']} GB VRAM"
             if gpu.get("vram_gb") else
             f"{profile.get('ram_gb', 0)} GB system RAM")
    head = (f"{profile.get('cores', 1)} cores, {where} → "
            f"~{usable} GB honestly usable ({basis})")
    reason_entry = {
        "model": reason[0], "size_gb": reason[1],
        "why": ("same weights as chat — counted once"
                if reason[1] == 0 else
                f"{head}; the reasoner runs on dwell, so "
                f"it may be heavier than chat: "
                f"{reason[0]}.")}
    if brain == "wici":
        model, footprint = wici_reason_pick(profile)
        combined, _vram, _uram = _wici_pools(profile)
        beta = wici_fulcrum(
            wici_cpu_rate(profile.get("cores", 1)),
            WICI_GPU_EXPERT_RATE)
        reason_entry = {
            "model": model,
            "size_gb": 0.0 if model == chat[0] else footprint,
            "why": (f"{head}; WiCi sizing: the reasoner's "
                    f"experts live on both legs, so it is sized "
                    f"against the combined pool (~{combined} GB "
                    f"of VRAM + usable RAM) and split at the "
                    f"fulcrum beta* {round(beta, 3)} — {model} "
                    f"at ~{footprint} GB across the legs. "
                    "Rates ASSUMED; chat keeps the dense "
                    "sizing above.")}
    return {
        "chat": {"model": chat[0], "size_gb": chat[1],
                 "why": f"{head}; chat earns {chat[0]} — fast enough "
                        f"to talk, sized to what the box can hold."},
        "reason": reason_entry,
        "summarizer": {"model": summ[0], "size_gb": summ[1],
                       "why": "the inflow manager stays tiny on "
                              "every box — breadth is its job, not "
                              "depth."},
        "usable_gb": usable, "basis": basis,
    }


# The FLOOR row — minimum requirements as measured precedent,
# not aspiration. The repo's own screenshots
# (glazing_chromebook_success.png) show this app's tool loop
# running live on a custom Chromebook build: Intel i3, no
# discrete VRAM, a 1.5B-class model carried entirely by system
# RAM — "working slowly but working", stable, no thrashing.
# Basic use stays usable on poor hardware because the internal
# model rings scale the answer: the tiny summarizer takes the
# breadth first, the small chat model handles basic use, and
# the reasoner is spent only on dwell and deep asks.
MINIMUM_PROFILE = {
    "chat": "1.5B-class, full CPU (e.g. qwen2.5:1.5b)",
    "summarizer": "1B-class tiny (gemma3:1b)",
    "reason": "the chat weights, on dwell — no second download",
    "hardware": "2+ cores, ~4 GB RAM, no GPU required",
    "evidence": "repo screenshot glazing_chromebook_success.png:"
                " live TOOL:shell:exec intercept on an i3"
                " Chromebook, 1.5B on system RAM, stable",
}


# --- The plan --------------------------------------------------------------

def _step(sid, title, why, commands=(), needs="user", min_level=1,
          network=False, disk_gb=0.0, download_gb=0.0, minutes=1,
          kind="run", note=""):
    return {"id": sid, "title": title, "why": why,
            "commands": list(commands), "needs": needs,
            "min_level": min_level, "network": network,
            "disk_gb": disk_gb, "download_gb": download_gb,
            "minutes": minutes, "kind": kind, "note": note}


def build_plan(profile, choices, src_dir=""):
    """The whole thread, as data. choices: mode home|system, brain
    ollama|llamacpp|wici|none, network local|lan|tailnet,
    api_tiers bool, chat_doors bool, pair bool, role
    parent|daughter|hybrid.
    src_dir is where the running app's tree lives (for copy steps).
    """
    mode = choices.get("mode", "home")
    brain = choices.get("brain", "ollama")
    home = profile.get("home", "~")
    root = "~/ai-core" if mode == "home" else "/opt/ai-core"
    rec = recommend_models(profile, brain=brain)
    wici = wici_details(profile, rec["reason"]["model"]) \
        if brain == "wici" else None
    steps = [
        _step("look", "Look at the box",
              "Read-only inspection: distro, cores, RAM, GPU, "
              "disk, home. Nothing changes.",
              needs="none", min_level=0, minutes=1),
    ]
    if mode == "home":
        steps.append(_step(
            "dirs", "Make the home tree",
            f"Everything lives under {root} — the home-folder "
            "minimum. No system directories are touched.",
            commands=[f"mkdir -p {root}/bin {root}/keys "
                      f"{root}/logs {root}/state"],
            disk_gb=0.01, minutes=1))
    else:
        steps.append(_step(
            "dirs", "Make the system tree",
            f"The full install lives under {root} with system "
            "systemd units — the original install.sh shape.",
            commands=[f"sudo mkdir -p {root}"],
            needs="sudo", min_level=2, disk_gb=0.01, minutes=1))
    steps.append(_step(
        "deps-check", "Check the Python/GTK floor",
        "The app needs Python 3, PyGObject and GTK4 present; "
        "checking costs nothing.",
        commands=['python3 -c "import gi, json, sqlite3"'],
        minutes=1))
    deps_cmd = _DEPS.get(profile.get("pkg_mgr") or "")
    if deps_cmd:
        steps.append(_step(
            "deps-install", "Install system packages (only if the "
            "check failed)",
            "GTK4/PyGObject/ffmpeg via the box's own package "
            "manager. This is the one step home-minimum mode "
            "cannot do for you — system packages are system "
            "changes, so the step waits at the sudo line.",
            commands=[deps_cmd], needs="sudo", min_level=2,
            network=True, disk_gb=0.4, download_gb=0.25, minutes=6))
    else:
        steps.append(_step(
            "deps-install", "Install system packages (guided)",
            "Package manager not recognized — install Python 3 + "
            "PyGObject + GTK4 + ffmpeg with your distro's tools; "
            "the check step above says when you're done.",
            needs="sudo", min_level=2, kind="guided", minutes=6))
    # The brain.
    if brain == "ollama":
        if mode == "home":
            arch = profile.get("arch", "x86_64")
            tgz = "arm64" if "arm" in arch or "aarch" in arch \
                else "amd64"
            steps.append(_step(
                "brain", "Install Ollama, user-space",
                "The official tarball unpacked under ~/ai-core — "
                "no service, no system path, removable by deleting "
                "a folder.",
                commands=[
                    f"curl -L https://ollama.com/download/"
                    f"ollama-linux-{tgz}.tgz | tar -xz -C {root}"],
                network=True, disk_gb=1.6, download_gb=1.3,
                minutes=5))
            pull = f"{root}/bin/ollama pull"
            serve_note = ""
        else:
            steps.append(_step(
                "brain", "Install Ollama (official installer)",
                "The ollama.com installer: binary + a system "
                "service. The standard shape on a system install.",
                commands=["curl -fsSL https://ollama.com/install.sh "
                          "| sh"],
                needs="sudo", min_level=2, network=True,
                disk_gb=1.6, download_gb=1.3, minutes=5))
            pull = "ollama pull"
            serve_note = ""
        cmds, seen = [], set()
        for slot in ("chat", "reason", "summarizer"):
            m = rec[slot]["model"]
            if m not in seen:
                seen.add(m)
                cmds.append(f"{pull} {m}")
        total_dl = sum(rec[s]["size_gb"] for s in ("chat", "reason", "summarizer"))
        steps.append(_step(
            "models", "Pull the sized models",
            "Properly sized to this box (see the Models reasoning "
            "in the plan header). Sizes are download estimates." +
            serve_note,
            commands=cmds, network=True, disk_gb=total_dl,
            download_gb=total_dl,
            minutes=max(2, int(total_dl * 1.5))))
    elif brain == "llamacpp":
        steps.append(_step(
            "brain", "Build llama.cpp (the router equivalent)",
            "llama-server with --models-dir does the same routing "
            "job as Ollama for GGUF weights. Building takes a "
            "while; a prebuilt llama-server dropped into "
            f"{root}/bin is equally welcome.",
            commands=[
                f"git clone https://github.com/ggml-org/llama.cpp "
                f"{root}/llama.cpp",
                f"cmake -B {root}/llama.cpp/build "
                f"-S {root}/llama.cpp",
                f"cmake --build {root}/llama.cpp/build -j"],
            network=True, disk_gb=1.2, download_gb=0.2, minutes=20))
        steps.append(_step(
            "models", "Fetch GGUF weights (guided)",
            "Download the recommended models as GGUF files into "
            f"{root}/models: " + ", ".join(
                f"{rec[s]['model']} (~{rec[s]['size_gb']} GB)"
                for s in ("chat", "reason", "summarizer")
                if rec[s]["size_gb"] > 0) +
            ". Any GGUF source you trust; sizes are estimates.",
            kind="guided", network=True,
            disk_gb=sum(rec[s]["size_gb"] for s in ("chat", "reason", "summarizer")),
            download_gb=sum(rec[s]["size_gb"] for s in ("chat", "reason", "summarizer")),
            minutes=10))
    elif brain == "wici":
        fd = wici["feed"]
        split_line = (
            f"Seesaw split for the reasoner "
            f"({rec['reason']['model']}, ~{wici['reason_gb']} GB "
            f"of experts): beta* {wici['beta']} — GPU leg holds "
            f"~{wici['gpu_gb']} GB, CPU leg ~{wici['cpu_gb']} GB, "
            f"sized against the combined VRAM+RAM pool. "
            f"{wici['rate_basis']}")
        if wici["lead_leg"] == "cpu":
            split_line += (
                " Free-range inversion: on this box the CPU "
                "leg leads the experts — leadership follows "
                "the rates, never a fixed GPU-first rule.")
        feed_line = (
            f"SSD feed bound: at ASSUMED {fd['cache_hit']:.0%} "
            f"expert-cache locality and an ASSUMED "
            f"{fd['drive_gb_s']:g} GB/s NVMe stream, "
            f"~{fd['streamed_gb_per_token']} GB streams per "
            f"token → the feed caps the reasoner near "
            f"{fd['bound_tok_s']} tok/s no matter how the "
            f"split sits. {wici['patience_cost']['note']}")
        if wici["faux"]:
            gpu = profile.get("gpu") or {}
            gpu_desc = ("no GPU at all" if not gpu else
                        f"a {gpu.get('vendor', 'unknown')} GPU "
                        f"({gpu.get('name', 'unnamed')})")
            steps.append(_step(
                "brain", "WiCi brain — FAUX on this box (guided)",
                "FAUX — no Nvidia detected. WiCi's InferSSD "
                "engine is CUDA-only on Linux, and this box "
                f"has {gpu_desc} — so for this brain nothing "
                "is fetched, built, or run, and no model "
                "downloads appear in this plan. What the plan "
                "carries, honestly labeled, is the split it "
                "WOULD use on an Nvidia box. " + split_line +
                " " + feed_line,
                kind="guided", minutes=0))
        else:
            steps.append(_step(
                "brain", "WiCi brain — InferSSD engine (guided)",
                "WiCi's InferSSD is an open-source llama.cpp "
                "fork (Apache-2.0) that streams MoE experts "
                "from SSD while the dense path stays resident "
                "on the GPU. Linux builds are CUDA-only. "
                "Guided-manual: fetch and build InferSSD from "
                "WiCi's own project distribution yourself — "
                "no mirror is named here on purpose — then "
                "point it at the GGUF weights from the models "
                "step. " + split_line,
                kind="guided", network=True, minutes=15))
            dl = sum(rec[s]["size_gb"]
                     for s in ("chat", "reason", "summarizer"))
            steps.append(_step(
                "models", "Fetch GGUF weights (guided)",
                "Download the recommended models as GGUF "
                f"files into {root}/models: " + ", ".join(
                    f"{rec[s]['model']} (~{rec[s]['size_gb']} GB)"
                    for s in ("chat", "reason", "summarizer")
                    if rec[s]["size_gb"] > 0) +
                ". Any GGUF source you trust; sizes are "
                "estimates. The reasoner is the WiCi-sized "
                "one — its experts live on both legs, and "
                "the summarizer rides the CPU leg.",
                kind="guided", network=True, disk_gb=dl,
                download_gb=dl, minutes=10))
            steps.append(_step(
                "seesaw", "WiCi seesaw setting (from the "
                "fulcrum)",
                f"Set the CPU-MoE share to beta* "
                f"{wici['beta']}: about "
                f"{round(wici['beta'] * 100):g}% of the "
                "reasoner's expert layers ride the CPU leg, "
                "the rest stay on the GPU leg. llama.cpp's "
                "--n-cpu-moe takes a layer COUNT — use "
                "round(beta* × the model's expert-layer "
                "count); layer counts are not in this plan's "
                "model data, so the percentage is the setting "
                "this plan can honestly carry. " + feed_line,
                kind="config", minutes=1,
                note=f"beta* {wici['beta']} · GPU "
                     f"{wici['gpu_gb']} GB · CPU "
                     f"{wici['cpu_gb']} GB · feed bound "
                     f"~{fd['bound_tok_s']} tok/s"))
    else:
        steps.append(_step(
            "brain", "No local brain (your call)",
            "Chat will lean on API tiers if you add them, and "
            "stay silent where nothing can answer. You can thread "
            "a brain in later — the plan is re-runnable.",
            kind="config", minutes=0))
    # The app tree + services.
    if mode == "home":
        steps.append(_step(
            "app-tree", "Copy the app tree home",
            "The client, core and rings, copied under ~/ai-core. "
            "Your running copy stays where it is.",
            commands=[f"cp -r {src_dir}/app {src_dir}/core "
                      f"{src_dir}/rings {src_dir}/config.json "
                      f"{root}/"] if src_dir else [],
            disk_gb=0.01, minutes=1))
        steps.append(_step(
            "services", "User services (guided)",
            "One user-level systemd unit per ring service, "
            "generated by the app at run time under "
            "~/.config/systemd/user, enabled with "
            "systemctl --user — no sudo, and they die with your "
            "session's choosing, not the box's.",
            kind="guided", minutes=3))
    else:
        steps.append(_step(
            "app-tree", "Run the system installer",
            "install.sh: tree to /opt/ai-core, units to systemd, "
            "validation at the end. The original path, unchanged.",
            commands=[f"cd {src_dir}/.. && sudo ./install.sh"]
            if src_dir else ["sudo ./install.sh"],
            needs="sudo", min_level=2, disk_gb=0.01, minutes=4))
    if choices.get("api_tiers"):
        steps.append(_step(
            "api-tiers", "API tiers for redundancy (optional)",
            "Add endpoint plugs in the Models view — OpenRouter, "
            "Nous, a custom endpoint. Keys are written to this "
            "box's local secrets file (0600), never logged, never "
            "required. Free tiers first in the recommended order; "
            "nothing on this step buys anything.",
            kind="config", minutes=2))
    if choices.get("chat_doors"):
        steps.append(_step(
            "chat-doors", "Chat doors — Telegram / Discord (guided)",
            "Guided-manual, honestly: the app cannot sign you up. "
            "For Telegram: talk to @BotFather, /newbot, copy the "
            "token it gives you into the Setup door's card — it "
            "lands in the local secrets file and the gateway "
            "config the app writes. Discord: create an application "
            "in the developer portal, add a bot, paste its token "
            "the same way. What the app automates is the config "
            "writing; the accounts are yours to make.",
            kind="guided", minutes=5))
    net = choices.get("network", "local")
    if net == "lan":
        steps.append(_step(
            "network", "LAN serving — a named boundary",
            "v1 services bind loopback, and a checkbox doesn't "
            "get to change that quietly: LAN exposure is a "
            "deliberate, separately-reviewed step (it exists as "
            "a self-maintenance proposal in the full design). "
            "This plan keeps serving local; the tailnet option "
            "is the sanctioned way off the box.",
            kind="config", minutes=0))
    elif net == "tailnet":
        steps.append(_step(
            "tailscale-install", "Install Tailscale (or equivalent)",
            "The tailnet is how this box is reached by its "
            "people and its agents — never the open internet.",
            commands=["curl -fsSL https://tailscale.com/install.sh "
                      "| sh"],
            needs="sudo", min_level=2, network=True, disk_gb=0.1,
            download_gb=0.05, minutes=4))
        steps.append(_step(
            "tailscale-up", "Join the tailnet (you authenticate)",
            "tailscale up opens your browser to sign in — the "
            "app cannot and should not do that part. Run it, "
            "approve the box, come back.",
            commands=["tailscale up"], kind="guided", minutes=3))
    steps.append(_step(
        "ssh-key", "Generate this box's SSH key",
        "An ed25519 keypair for the box itself, so other boxes "
        "and agents pair TO it deliberately.",
        commands=['test -f ~/.ssh/ai-core || ssh-keygen -t ed25519 '
                  '-f ~/.ssh/ai-core -N "" -C "ai-core@$(hostname)"'],
        minutes=1))
    if choices.get("pair"):
        steps.append(_step(
            "pairer", "Pair an agent (you carry the key)",
            "Use the pairing card below: paste the agent's public "
            "key (Muse's, to start), read its fingerprint back, "
            "press write — the pairer script installs that one "
            "key, restricted to tailnet addresses. Trust is "
            "never generated silently; it is carried, by you, "
            "between boxes.",
            kind="config", minutes=2))
    role = choices.get("role", "parent")
    steps.append(_step(
        "role", f"Role: {role}",
        {"parent": "The full app; records daughters' briefs.",
         "daughter": "Senses + briefs, tiny footprint; the parent "
                     "endpoint goes in Options → Role & daughters.",
         "hybrid": "Both roles on this box — the self-test "
                   "shape."}[role],
        kind="config", minutes=0))
    totals = {
        "disk_gb": round(sum(s["disk_gb"] for s in steps), 2),
        "download_gb": round(sum(s["download_gb"] for s in steps), 2),
        "minutes": sum(s["minutes"] for s in steps),
        "network_steps": sum(1 for s in steps if s["network"]),
        "money": "$0 by default — API tiers are opt-in and priced "
                 "by their providers; nothing in this plan buys "
                 "anything.",
    }
    plan = {
        "profile": profile, "choices": choices,
        "recommendations": rec, "steps": steps, "totals": totals,
        "minimums": MINIMUM_PROFILE,
        "limits": {
            # The approval layer knows two limits and shows both.
            "declared": {
                "chat_model": rec["chat"]["model"],
                "reason_model": rec["reason"]["model"],
                "summarizer_model": rec["summarizer"]["model"],
                "mode": mode, "network": choices.get(
                    "network", "local"),
                "privilege_ceiling": "each sudo step is named "
                                     "before it runs; nothing "
                                     "silent",
            },
            "actual": {
                "cores": profile.get("cores"),
                "ram_gb": profile.get("ram_gb"),
                "vram_gb": (profile.get("gpu") or {}).get(
                    "vram_gb"),
                "usable_gb": rec["usable_gb"],
                "basis": rec["basis"],
                "disk_free_gb": profile.get("disk_free_gb"),
            },
            "rule": "To push past a declared limit, provide "
                    "power and data — a bigger local model, "
                    "more hardware headroom, an API tier, more "
                    "storage. The app never just raises a "
                    "number.",
        },
        "footprint": (
            f"home minimum: everything under {root} "
            f"(~{totals['disk_gb']} GB incl. brain + models); the "
            "only system change on the table is the GTK package "
            "step, held at the sudo line."
            if mode == "home" else
            f"system install: {root} + systemd units "
            f"(~{totals['disk_gb']} GB incl. brain + models)."),
    }
    if wici is not None:
        plan["wici"] = wici
        declared = plan["limits"]["declared"]
        declared["brain"] = (
            "wici — FAUX (no Nvidia detected)" if wici["faux"]
            else "wici (Nvidia + InferSSD seesaw)")
        declared["wici_beta"] = wici["beta"]
        declared["wici_gpu_gb"] = wici["gpu_gb"]
        declared["wici_cpu_gb"] = wici["cpu_gb"]
        declared["wici_feed_tok_s"] = wici["feed"]["bound_tok_s"]
        declared["wici_patience_delta_pct"] = \
            wici["patience_cost"]["est_latency_delta_pct"]
    return plan


def steps_for_level(plan, level):
    """(runnable, held) at a privilege comfort level. A step is
    held when its privilege floor sits above the chosen level —
    held steps are announced, never silently dropped."""
    runnable = [s for s in plan["steps"] if s["min_level"] <= level]
    held = [s for s in plan["steps"] if s["min_level"] > level]
    return runnable, held


def render_script(plan, level):
    """The dry run: the whole plan as one bash script. Held steps
    are printed as comments with their commands — reading the
    script tells you exactly what a higher level would do."""
    t = plan["totals"]
    lines = [
        "#!/usr/bin/env bash",
        "# AI Core first-run plan — DRY RUN rendering.",
        f"# Cost up front: ~{t['disk_gb']} GB disk, "
        f"~{t['download_gb']} GB downloads, ~{t['minutes']} min, "
        f"{t['network_steps']} steps need the network.",
        f"# Money: {t['money']}",
        f"# Privilege level for this rendering: {level} "
        "(0 look · 1 user-space · 2 ask-per-sudo · 3 session grant)",
        "set -euo pipefail", "",
    ]
    wici = plan.get("wici")
    if wici:
        fd = wici["feed"]
        lines.append(
            f"# WiCi seesaw: beta* {wici['beta']} — GPU leg "
            f"{wici['gpu_gb']} GB, CPU leg {wici['cpu_gb']} GB "
            f"of the reasoner"
            + (" (CPU leg leads — free-range inversion)"
               if wici["lead_leg"] == "cpu" else ""))
        lines.append(
            "# WiCi legs: " + " · ".join(
                f"{leg['slot']} → "
                f"{'+'.join(leg['legs']).upper()}"
                for leg in wici["legs"]))
        lines.append(
            f"# WiCi feed bound: "
            f"~{fd['streamed_gb_per_token']} GB/token at "
            f"ASSUMED {fd['cache_hit']:.0%} cache locality, "
            f"ASSUMED {fd['drive_gb_s']:g} GB/s drive → "
            f"~{fd['bound_tok_s']} tok/s ceiling; patience "
            f"cost {wici['patience_cost']['est_latency_delta_pct']:+g}% "
            "reason-token latency vs a resident all-GPU path "
            "(ASSUMED rates).")
        if wici["faux"]:
            lines.append("# WiCi: FAUX — no Nvidia detected; "
                         "plan-only, nothing fetches or runs.")
        lines.append("")
    runnable, held = steps_for_level(plan, level)
    held_ids = {s["id"] for s in held}
    for s in plan["steps"]:
        lines.append(f"# --- {s['title']} [{s['needs']}]")
        if s["id"] in held_ids:
            lines.append(f"# HELD at level {level} — needs "
                         f"privilege level {s['min_level']}:")
            for c in s["commands"]:
                lines.append(f"#   {c}")
            if not s["commands"]:
                lines.append("#   (no commands — guided/config)")
        elif s["kind"] in ("guided", "config"):
            lines.append(f"# {s['kind'].upper()}: {s['why']}")
            for c in s["commands"]:
                lines.append(c)
        else:
            lines.extend(s["commands"] or
                         ["# (inspection only — no commands)"])
        lines.append("")
    return "\n".join(lines)


# --- Pairing ---------------------------------------------------------------

_KEY_CHARS = re.compile(r"^[A-Za-z0-9+/= .@_\-]+$")


def key_fingerprint(pubkey_line):
    """OpenSSH-style SHA256 fingerprint of a public key line."""
    parts = pubkey_line.strip().split()
    if len(parts) < 2:
        raise ValueError("not a public key line")
    blob = base64.b64decode(parts[1])
    digest = base64.b64encode(hashlib.sha256(blob).digest())
    return "SHA256:" + digest.decode().rstrip("=")


def pairer_script(pubkey_line, label):
    """The exportable pairer: installs ONE pasted public key into
    ~/.ssh/authorized_keys, restricted to tailnet source addresses
    (from="100.64.0.0/10" — the pattern this lab pairs Muse by).
    Idempotent; prints the fingerprint it installed."""
    pubkey_line = pubkey_line.strip()
    if not pubkey_line.startswith(("ssh-ed25519 ", "ssh-rsa ",
                                   "ecdsa-sha2-")) \
            or not _KEY_CHARS.match(pubkey_line):
        raise ValueError("that doesn't look like an SSH public key")
    fp = key_fingerprint(pubkey_line)
    safe_label = re.sub(r"[^A-Za-z0-9 _\-]", "", label)[:40] \
        or "agent"
    return f"""#!/usr/bin/env bash
# AI Core pairer — pair "{safe_label}" to this box.
# Installs ONE public key, reachable from tailnet addresses only.
# Fingerprint (check it against the agent's own report): {fp}
set -euo pipefail
KEY='{pubkey_line}'
LINE='from="100.64.0.0/10" '"$KEY"
mkdir -p ~/.ssh && chmod 700 ~/.ssh
touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys
if grep -qF "$KEY" ~/.ssh/authorized_keys; then
  echo "already paired: {safe_label} ({fp})"
else
  echo "$LINE" >> ~/.ssh/authorized_keys
  echo "paired: {safe_label} ({fp}) — tailnet addresses only"
fi
"""


# --- Local secrets -----------------------------------------------------------

def config_dir():
    return Path.home() / ".config" / "ai-core"


def _secrets_path(base=None):
    return Path(base) if base else config_dir() / "secrets.json"


def save_secret(name, value, base=None):
    """Write one secret into the local secrets file (0600).
    Returns the path. Values are never logged anywhere."""
    if not re.fullmatch(r"[a-z0-9\-]+", name):
        raise ValueError("secret names are [a-z0-9-]")
    path = _secrets_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except (ValueError, OSError):
            data = {}
    data[name] = value
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
    os.chmod(path, 0o600)
    return str(path)


def load_secret(name, base=None):
    try:
        data = json.loads(_secrets_path(base).read_text())
        return data.get(name)
    except (ValueError, OSError):
        return None


def generate_pairing_secret():
    """A fresh pairing secret, shown once by the Setup door and
    carried by the owner to the paired box. Never logged."""
    import secrets
    return secrets.token_hex(16)


# --- Config editors ----------------------------------------------------------

def validate_config_text(text):
    """Validate an edited config.json before it may be saved.
    Returns (ok, problems). Pure — no I/O."""
    problems = []
    try:
        cfg = json.loads(text)
    except ValueError as e:
        return False, [f"not JSON: {e}"]
    if not isinstance(cfg, dict):
        return False, ["the config must be one JSON object"]
    ports = cfg.get("mcp_ports")
    if ports is not None:
        if not isinstance(ports, dict):
            problems.append("mcp_ports must be an object")
        else:
            if set(ports) != set(SERVICE_PORTS):
                problems.append(
                    "mcp_ports keys differ from the ring services: "
                    f"config has {sorted(ports)}, the wire contract "
                    f"has {sorted(SERVICE_PORTS)}")
            for name, port in ports.items():
                if not isinstance(port, int) \
                        or not (1 <= port <= 65535):
                    problems.append(f"mcp_ports.{name} is not a "
                                    "valid port")
    return not problems, problems


def probe_config_ports(text, call=None):
    """Compare an edited config's ports against the LIVE services'
    health reports. Returns one line per service — the validate-
    before-save receipt. Never raises."""
    from core.protocol import mcp_call as _call
    call = call or _call
    try:
        cfg = json.loads(text)
        ports = cfg.get("mcp_ports") or {}
    except ValueError:
        return ["config doesn't parse — fix that first"]
    lines = []
    for name in sorted(SERVICE_PORTS):
        want = ports.get(name, SERVICE_PORTS[name])
        resp = call(SERVICE_PORTS[name], {"action": "health"},
                    timeout=2)
        if resp.get("status") == "error":
            lines.append(f"{name}: not answering on "
                         f"{SERVICE_PORTS[name]} (config says "
                         f"{want})")
        elif "port" in resp:
            mark = "ok" if resp["port"] == want else "MISMATCH"
            lines.append(f"{name}: live on {resp['port']}, config "
                         f"says {want} — {mark}")
        else:
            lines.append(f"{name}: answering on "
                         f"{SERVICE_PORTS[name]} (no in-band port "
                         f"report; config says {want})")
    return lines
