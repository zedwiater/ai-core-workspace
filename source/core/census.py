#!/usr/bin/env python3
"""census.py — AI Core capability census (refinement brick 1, 2026-11-17).

The Dream (Zak): an autonomous AI conduit that brings competent, relevant
AI into any system at any level, working with users to find balanced flow
for the hardware aptitude they have — setting expectations and
calculating joy along the way.

This script is the crawl-time census the conduit runs before it promises
anything. It measures EFFECTIVE capacity (cgroup quotas and contention,
not just nominal specs), inventories the runtimes and models actually on
the box, derives a parallel-task budget, and emits an EXPECTATION TABLE
per tier — for a human reader (expectations.md) and for a fellow AI user
(expectations.json). Every number that is an estimate is labeled one;
the calibration constants come from the reference install (Zak's home
stack, measured 2026-11-15..17) and are stated in the output.

Stdlib only. Read-only: it installs nothing, starts nothing, changes
nothing. Usage: python3 census.py [--out DIR]
"""
import glob, json, os, platform, shutil, subprocess, sys, time
import urllib.request

# --- probes ---------------------------------------------------------------

def cpu_probe():
    logical = os.cpu_count() or 1
    effective = float(logical)
    src = "nominal"
    try:  # cgroup v2
        raw = open("/sys/fs/cgroup/cpu.max").read().split()
        if raw[0] != "max":
            effective = min(effective, int(raw[0]) / int(raw[1]))
            src = "cgroup v2 cpu.max"
    except Exception:
        try:  # cgroup v1
            q = int(open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us").read())
            p = int(open("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read())
            if q > 0:
                effective = min(effective, q / p)
                src = "cgroup v1 cfs quota"
        except Exception:
            pass
    if src == "nominal" and os.path.exists("/sys/fs/cgroup/cgroup.controllers"):
        src = "nominal (cgroup v2 present, no quota visible from inside)"
    try:
        load1 = os.getloadavg()[0]
    except Exception:
        load1 = 0.0
    return {"logical_threads": logical, "effective_threads": round(effective, 2),
            "effective_source": src, "load1": round(load1, 2),
            "load_per_effective_thread": round(load1 / max(effective, 0.1), 2)}

def ram_probe():
    info = {}
    try:
        for line in open("/proc/meminfo"):
            k, v = line.split(":", 1)
            info[k.strip()] = int(v.split()[0]) // 1024  # MB
    except Exception:
        pass
    total = info.get("MemTotal", 0)
    avail = info.get("MemAvailable", 0)
    eff = total
    src = "nominal"
    try:
        raw = open("/sys/fs/cgroup/memory.max").read().strip()
        if raw != "max":
            eff = min(eff, int(raw) // (1024 * 1024))
            src = "cgroup v2 memory.max"
    except Exception:
        pass
    return {"total_mb": total, "available_mb": avail, "effective_mb": eff,
            "effective_source": src, "swap_mb": info.get("SwapTotal", 0)}

def gpu_probe():
    gpus = []
    for card in sorted(glob.glob("/sys/class/drm/card[0-9]*")):
        try:
            vendor = open(os.path.join(card, "device/vendor")).read().strip()
        except Exception:
            continue
        vram = 0
        for f in ("mem_info_vram_total",):
            try:
                vram = int(open(os.path.join(card, "device", f)).read()) // (1024 ** 3)
            except Exception:
                pass
        vendor_name = {"0x1002": "AMD", "0x10de": "NVIDIA",
                       "0x8086": "Intel"}.get(vendor, vendor)
        gpus.append({"vendor": vendor_name,
                     "vram_gb": vram,
                     # Consumers greet by name; a probe that emits no
                     # name crashed the installer narration AND the
                     # landing greeting on real AMD hardware
                     # (2026-11-17). Always emit one.
                     "name": f"{vendor_name} GPU"
                             + (f" ({vram} GB)" if vram else "")})
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.run(["nvidia-smi", "--query-gpu=memory.total",
                                  "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True, timeout=5).stdout
            for i, line in enumerate(out.strip().splitlines()):
                if i < len(gpus):
                    gpus[i]["vram_gb"] = int(line) // 1024
        except Exception:
            pass
    return gpus

def _py_has(mod):
    """Env-aware (same rule as pipes.py): the stack's modules live in the
    pythons its own services run, not necessarily the system python."""
    import glob as _glob, re as _re
    cands = [sys.executable]
    for unit in _glob.glob(os.path.expanduser("~/.config/systemd/user/*.service")):
        try:
            for m in _re.findall(r"(/[^\s\"']*/bin/python3?)", open(unit).read()):
                if m not in cands:
                    cands.append(m)
        except Exception:
            pass
    for py in cands[:8]:
        try:
            if subprocess.run([py, "-c", f"import {mod}"],
                              capture_output=True, timeout=6).returncode == 0:
                return True
        except Exception:
            pass
    return False

def _https_reachable(host):
    try:
        req = urllib.request.Request(f"https://{host}/",
                                     headers={"User-Agent": "ai-core-census/0.1"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False

def runtime_probe():
    rt = {"ollama": {"binary": shutil.which("ollama") is not None, "api": False,
                     "models": []},
          "llama_cpp": shutil.which("llama-server") is not None or
                       os.path.exists(os.path.expanduser("~/llama.cpp/build/bin/llama-server")),
          "ffmpeg": shutil.which("ffmpeg") is not None,
          "web_search": _https_reachable("lite.duckduckgo.com"),
          "whisper": shutil.which("whisper") is not None or _py_has("whisper")
                     or _py_has("faster_whisper"),
          "espeak_ng": shutil.which("espeak-ng") is not None,
          "image_gen": os.path.exists(os.path.expanduser("~/george-lab/imgvenv")) or
                       shutil.which("sd") is not None}
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2) as r:
            data = json.loads(r.read().decode())
        rt["ollama"]["api"] = True
        for m in data.get("models", []):
            rt["ollama"]["models"].append(
                {"name": m["name"], "size_gb": round(m.get("size", 0) / 1e9, 1)})
    except Exception:
        pass
    ggufs = []
    for root in ("~/wave-sunday/data/models", "~/.ollama/models", "~/models",
                 "~/ai-core/models"):
        for p in glob.glob(os.path.expanduser(root) + "/**/*.gguf", recursive=True):
            if "mmproj" in os.path.basename(p):
                continue
            ggufs.append({"name": os.path.basename(p),
                          "size_gb": round(os.path.getsize(p) / 1e9, 1),
                          "vl_projector": os.path.exists(
                              os.path.join(os.path.dirname(p),
                                           "mmproj-model-f16.gguf")) or
                              bool(glob.glob(os.path.join(
                                  os.path.dirname(p), "mmproj*.gguf")))})
    rt["gguf_models"] = ggufs
    return rt

# --- model classification ---------------------------------------------------

def params_b(name, size_gb):
    n = name.lower()
    for tok in ("30b", "32b", "27b", "14b", "13b", "12b", "9b", "8b", "7b",
                "4b", "3b", "2b", "1b"):
        if tok in n:
            return float(tok[:-1])
    return max(1.0, size_gb / 0.55)  # Q4 ≈ 0.55 GB per B params

def classify(models):
    tiers = {"conversation": None, "deep": None, "vision": None}
    for m in models:
        p = params_b(m["name"], m["size_gb"])
        m = dict(m, params_b=p)
        n = m["name"].lower()
        is_vl = m.get("vl_projector") or any(
            t in n for t in ("vl", "vision", "llava", "gemma-3", "moondream"))
        if is_vl and tiers["vision"] is None:
            tiers["vision"] = m
        if p >= 20:
            if tiers["deep"] is None:
                tiers["deep"] = m
        elif 5 <= p <= 17:
            if tiers["conversation"] is None:
                tiers["conversation"] = m
            elif tiers["deep"] is None and p >= 12:
                tiers["deep"] = m
        elif p < 5 and tiers["conversation"] is None:
            tiers["conversation"] = m
    return tiers

# --- budget + expectations ----------------------------------------------------

def tps_est(params, threads):
    """Rough CPU tok/s for a Q4 model. Calibrated on the reference install:
    7B Q4 @16 threads ≈ 7.5 tok/s (george-chat, measured); 4B VL @8 threads
    ≈ 10 tok/s of generation inside 24-34s seats (measured). Estimate."""
    import math
    return round(30.0 / max(params, 0.5) * math.sqrt(max(threads, 1) / 4.0), 1)

def latency_class(first_token_s, tps):
    if first_token_s <= 1 and tps >= 8:
        return "conversational (answers feel immediate)"
    if first_token_s <= 10:
        return "conversational (a breath before the answer)"
    if first_token_s <= 60:
        return "deliberate (announced wait, streamed progress)"
    return "batch (announced, heartbeat updates, minutes)"

def build(c):
    cpu, ram, gpus, rt = c["cpu"], c["ram"], c["gpus"], c["runtimes"]
    models = rt["ollama"]["models"] + rt["gguf_models"]
    tiers = classify(models)
    threads = cpu["effective_threads"]
    ram_gb = ram["effective_mb"] / 1024.0
    vram = max([g["vram_gb"] for g in gpus], default=0)

    reserve_threads = 1.0
    usable_threads = max(0.0, threads - reserve_threads)
    conv = tiers["conversation"]
    conv_threads = 0
    conv_mode = "script-floor"
    conv_gpu = False
    if conv:
        # The reference install's measured conversation seat is 16 threads;
        # claiming more starves the task seats the budget then promises.
        conv_threads = max(2.0, min(usable_threads, usable_threads * 0.6, 16.0)) \
            if usable_threads >= 2 else usable_threads
        if vram >= conv["size_gb"] * 1.15:
            conv_gpu = True
            conv_mode = "resident (GPU seat, pinned)"
        elif vram and conv["size_gb"] <= vram * 1.6:
            conv_gpu = True
            conv_mode = "resident (GPU+CPU split seat, pinned)"
        elif ram_gb >= conv["size_gb"] * 1.6 and usable_threads >= 2:
            conv_mode = "resident (CPU seat, pinned)"
        else:
            conv_mode = "on-demand (announced load, then resident)"
    task_threads = max(0.0, usable_threads - conv_threads)
    seats = int(task_threads // 4) if conv else int(usable_threads // 4)
    budget = {
        "conversation_seat": 1 if conv else 0,
        "parallel_model_task_seats": seats,
        "script_tasks": "not seat-bound (deterministic legs; dozens in practice)",
        "max_parallel_model_tasks": (1 if conv else 0) + seats,
        "basis": (f"{threads} effective threads - {reserve_threads} OS reserve"
                  f" - {conv_threads:.1f} conversation seat = {task_threads:.1f}"
                  " threads for task seats at 4 threads/seat (estimate)"),
    }

    def tier_row(name, model, kind):
        if model is None:
            return {"tier": name, "status": "unavailable",
                    "falls_to": "script floor",
                    "expectation": "Handled by deterministic scripts; no model is promised."}
        th = conv_threads if kind == "conversation" else min(8.0, max(2.0, task_threads or 4.0))
        tps = tps_est(model["params_b"], th)
        load_s = round(model["size_gb"] * (2.5 if kind != "conversation" or not conv_gpu else 1.2))
        return {"tier": name, "model": model["name"], "params_b": model["params_b"],
                "status": conv_mode if kind == "conversation" else "on-demand (announced seat)",
                "est_load_s": load_s, "est_tok_s_cpu": tps,
                "latency": latency_class(0.5 if kind == "conversation" and "resident" in conv_mode else load_s, tps),
                "announcement": ANNOUNCE[kind].format(load=load_s)}

    table = [tier_row("conversation", conv, "conversation"),
             tier_row("deep", tiers["deep"] or conv, "deep"),
             tier_row("vision", tiers["vision"], "vision")]
    if tiers["deep"] is None and conv is not None:
        table[1]["note"] = "No deep-class model on the box; deep work falls to the conversation model, stated plainly."
    table.append({"tier": "image generation",
                  "status": "on-demand (slow lane, heartbeat)" if rt["image_gen"] else "unavailable",
                  "expectation": "Minutes per picture on CPU; progress is streamed, there is no silent wait."
                                 if rt["image_gen"] else "No image runtime found; the conduit says so instead of pretending."})
    table.append({"tier": "audio (listen/speak)",
                  "status": "service" if rt["whisper"] else "limited",
                  "expectation": "Whisper-class listening where present; speech via system tools. "
                                 "Media plumbing (ffmpeg) alone is not a listening service, and the table says so."})
    table.append({"tier": "knowledge (web)",
                  "status": "available (free-tier search script)" if rt["web_search"] else "offline",
                  "expectation": "Answers at network speed (~1-2s fetches, measured on the low VM); snippets are leads, opening a page is verification. A small local model plus web reach is a capability, not a handicap."
                                 if rt["web_search"] else
                                 "No internet reach: stored model knowledge + system state/metrics only — narrower, stated plainly, still useful."})
    table.append({"tier": "script floor",
                  "status": "always available",
                  "expectation": "Deterministic scripts and voice commands carry the load at zero model cost. The floor never goes to zero."})
    return {"budget": budget, "tiers": table}

ANNOUNCE = {
    "conversation": "Your conversation model is resident — no load wait.",
    "deep": "Taking the deep seat now (~{load}s to load). I'll stream progress while it thinks.",
    "vision": "The sight organ is taking its seat for a short, capped review (~{load}s to load). Your conversation is not interrupted.",
}

try:  # the pairing is part of the crawl contract when available
    from core import pairing as _pairing_mod
except Exception:
    try:
        import pairing as _pairing_mod
    except Exception:
        _pairing_mod = None


def camera_probe(sys_root="/sys/class/video4linux"):
    """The machine's eyes: video capture devices, name + node,
    metadata only — no frames are ever read by a crawl. The
    first version of this crawl never looked, and reported a
    laptop with a webcam as a machine without one (Zak,
    2026-11-18)."""
    cams = []
    for node in sorted(glob.glob(os.path.join(sys_root, "video*"))):
        dev = "/dev/" + os.path.basename(node)
        try:
            name = open(os.path.join(node, "name")).read().strip()
        except Exception:
            name = ""
        cams.append({"device": dev, "name": name or dev})
    return cams


def main():
    out_dir = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "."
    census = {"host": platform.node(), "os": f"{platform.system()} {platform.release()}",
              "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
              "cpu": cpu_probe(), "ram": ram_probe(), "gpus": gpu_probe(),
              "cameras": camera_probe(),
              "disk_free_gb": round(shutil.disk_usage(os.path.expanduser("~")).free / 1e9),
              "runtimes": runtime_probe()}
    census["expectations"] = build(census)
    if _pairing_mod is not None:
        try:
            census["pairing"] = _pairing_mod.pair(census)
        except Exception:
            pass
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "expectations.json"), "w") as f:
        json.dump(census, f, indent=1)
    md = [f"# Expectation table — {census['host']} ({census['ts']})", "",
          f"CPU: {census['cpu']['logical_threads']} logical / "
          f"{census['cpu']['effective_threads']} effective threads "
          f"({census['cpu']['effective_source']}); load {census['cpu']['load1']}",
          f"RAM: {census['ram']['effective_mb']} MB effective ({census['ram']['effective_source']}); "
          f"GPUs: {census['gpus'] or 'none detected'}; disk free {census['disk_free_gb']} GB", "",
          f"**Parallel-task budget:** {census['expectations']['budget']['max_parallel_model_tasks']} "
          f"model tasks at once (conversation seat "
          f"{census['expectations']['budget']['conversation_seat']} + "
          f"{census['expectations']['budget']['parallel_model_task_seats']} task seats); "
          f"script tasks are not seat-bound.",
          f"Basis: {census['expectations']['budget']['basis']}", "",
          "| Tier | Status | Expectation |", "|---|---|---|"]
    for t in census["expectations"]["tiers"]:
        exp = t.get("expectation") or t.get("announcement", "")
        if t.get("latency"):
            exp = f"{t['latency']}. {exp}"
        md.append(f"| {t['tier']} | {t['status']} | {exp} |")
    md += ["", "All tok/s and load figures are estimates, calibrated on the "
           "reference install (Zak's home stack) and labeled as such. The "
           "conduit announces a seat before it takes it; a silent hang is "
           "a bug, never a state."]
    with open(os.path.join(out_dir, "expectations.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md))

if __name__ == "__main__":
    main()
