#!/usr/bin/env python3
"""pairing.py — the installer's base function (Zak's definition,
2026-11-17): find out the hardware aptitude, pair it with a KNOWN
model, install that model, and set its layers appropriately and
its tiers against the talking model.

One function, used by the installer, the first-launch popup and
the landing greeting, so all three never disagree: aptitude in
(the census), a pairing out — the model, the seat it will take,
how many of its layers belong on the GPU, and what the tiers may
honestly promise against that talking model.

The model table carries KNOWN constants (parameter class, Q4_K_M
footprint, architecture layer count). Estimates are labeled as
estimates; a model whose layer count is not known gets no layer
plan rather than an invented one.
"""

# name -> known constants. size_gb is the Q4_K_M download/weights
# footprint; layers is the architecture's transformer layer count.
KNOWN_MODELS = [
    {"name": "qwen2.5:14b", "params_b": 14.0, "size_gb": 9.0, "layers": 48},
    {"name": "qwen3:14b", "params_b": 14.0, "size_gb": 9.3, "layers": 40},
    {"name": "qwen3.5:9b", "params_b": 9.0, "size_gb": 6.0, "layers": None},
    {"name": "qwen3:8b", "params_b": 8.0, "size_gb": 5.2, "layers": 36},
    {"name": "qwen2.5:7b", "params_b": 7.0, "size_gb": 4.7, "layers": 28},
    {"name": "qwen2.5:3b", "params_b": 3.0, "size_gb": 2.0, "layers": 36},
    {"name": "qwen2.5:1.5b", "params_b": 1.5, "size_gb": 1.0, "layers": 28},
]

# Seat policy (the census doctrine, applied to a pairing):
# full GPU fit needs headroom over the raw weights (KV + runtime);
# a split seat may lean on RAM but the model may not exceed the
# combined pool; a CPU seat needs the weights plus working room —
# AND the machine must stay a machine: the desktop, the app and
# the OS keep a reserve the model may not eat. (Learned the hard
# way on the reference laptop, 2026-11-17: an 8B paired onto 7 GB
# total left the desktop nothing, and the machine hard-locked.)
FULL_GPU_HEADROOM = 1.15
SPLIT_POOL = 1.0
CPU_HEADROOM = 1.3
OS_RESERVE_GB = 2.0


def _aptitude(census):
    ram_gb = (census.get("ram", {}).get("effective_mb") or 0) / 1024.0
    vrams = [g.get("vram_gb") or 0 for g in census.get("gpus", [])]
    # One talking model lives on one card: the largest single VRAM
    # is the GPU aptitude, never a sum across cards.
    vram_gb = max(vrams) if vrams else 0
    return ram_gb, vram_gb


def pair(census):
    """Aptitude -> pairing. Returns the talking model, its seat,
    its layer plan (gpu_layers of total, or None when the model's
    layer count is not a known constant), and the tier basis."""
    ram_gb, vram_gb = _aptitude(census)
    for m in KNOWN_MODELS:  # largest first: the best honest fit wins
        size = m["size_gb"]
        if vram_gb >= size * FULL_GPU_HEADROOM:
            mode, frac = "full GPU seat", 1.0
        elif vram_gb > 0 and (vram_gb + ram_gb) >= size \
                and vram_gb >= size * 0.25:
            mode = "GPU+CPU split seat"
            frac = min(0.85, vram_gb / (size * FULL_GPU_HEADROOM))
        elif (ram_gb - OS_RESERVE_GB) >= size * CPU_HEADROOM:
            mode, frac = "CPU seat", 0.0
        else:
            continue
        gpu_layers = None
        if m["layers"] is not None:
            gpu_layers = round(m["layers"] * frac)
        return {"model": m["name"], "params_b": m["params_b"],
                "size_gb": size, "mode": mode,
                "gpu_layers": gpu_layers, "total_layers": m["layers"],
                "aptitude": {"ram_gb": round(ram_gb, 1),
                             "vram_gb": vram_gb},
                "tier_basis": f"tiers are promised against "
                              f"{m['name']} on a {mode}"}
    # Below every known model: the floor still pairs — with the
    # smallest known model on a CPU seat and the honesty to say the
    # fit is nominal (the script floor carries the experience).
    m = KNOWN_MODELS[-1]
    return {"model": m["name"], "params_b": m["params_b"],
            "size_gb": m["size_gb"], "mode": "CPU seat (nominal fit)",
            "gpu_layers": 0, "total_layers": m["layers"],
            "aptitude": {"ram_gb": round(ram_gb, 1), "vram_gb": vram_gb},
            "tier_basis": f"tiers are promised against {m['name']} on a "
                          "nominal CPU seat; the script floor leads"}
