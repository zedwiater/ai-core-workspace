# --- AI Core module label ---
# Label-Name: governor
# Label-Origin: ai-core-workspace build (Zak/Muse)
# Label-Version: 1
# Label-Does: the resource budget for background work —
#   storage, RAM and load caps by tier, assessed honestly
#   before the dwell loop spends anything
# --- end label ---
"""The governor (Zak, 2026-11-18): background dwell and
roam must never compromise the machine the user is living
on — not its storage, not its RAM, not its responsiveness
— whether the user is working on it or it's sitting alone.

Three budgets, all tier-scaled, all READABLE (the dwell
status carries them, so the caps are a fact the user can
check, not a promise):

- storage: the dwell store (frames, clips, recordings)
  has a byte cap; pruning is oldest-first. Below a disk
  floor, grabbing stops entirely.
- RAM: when available memory falls under the floor, the
  loop pauses — the user's work owns the machine.
- load: when the 1-minute load says the user is busy,
  the cycle is skipped and the skip is LOGGED (throttled,
  never silent).

The loop already runs nice'd; the governor is what makes
"idle-time work" a measured claim instead of a hope.
"""
import os

RECORDINGS_DIR = os.path.expanduser("~/.cache/ai-core/recordings")


def budget_for(ram_gb):
    """Tier caps from the machine's size."""
    if ram_gb >= 24:
        cap_mb = 2048
    elif ram_gb >= 10:
        cap_mb = 1024
    else:
        cap_mb = 300
    return {"storage_cap_mb": cap_mb,
            "ram_floor_mb": 1536,
            "load_per_core": 0.9,
            "disk_floor_gb": 2.0}


def dir_bytes(path):
    total = 0
    if not os.path.isdir(path):
        return 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(
                    os.path.join(root, name))
            except OSError:
                pass
    return total


def _mem_available_mb():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
    except OSError:
        pass
    return None


def _load1():
    try:
        return os.getloadavg()[0]
    except (OSError, AttributeError):
        return None


def assess(dwell_dir, ram_gb, recordings_dir=RECORDINGS_DIR):
    """The pre-cycle verdict. ok=False always carries the
    reason — a throttled cycle is a logged fact."""
    budget = budget_for(ram_gb)
    used = dir_bytes(dwell_dir) + dir_bytes(recordings_dir)
    out = {"budget": budget,
           "used_mb": round(used / 1e6, 1),
           "load1": _load1(),
           "cores": os.cpu_count() or 1,
           "avail_ram_mb": _mem_available_mb(),
           "free_disk_gb": None,
           "ok": True, "reason": ""}
    try:
        st = os.statvfs(os.path.expanduser("~"))
        out["free_disk_gb"] = round(
            st.f_bavail * st.f_frsize / 1e9, 1)
    except OSError:
        pass
    if out["free_disk_gb"] is not None \
            and out["free_disk_gb"] < budget["disk_floor_gb"]:
        out["ok"] = False
        out["reason"] = (f"disk floor: {out['free_disk_gb']} GB "
                         f"free < {budget['disk_floor_gb']} GB "
                         f"floor — grabbing paused")
        return out
    if out["avail_ram_mb"] is not None \
            and out["avail_ram_mb"] < budget["ram_floor_mb"]:
        out["ok"] = False
        out["reason"] = (f"RAM floor: {out['avail_ram_mb']} MB "
                         f"available < {budget['ram_floor_mb']} "
                         f"MB floor — the user's work owns "
                         f"the machine")
        return out
    if out["load1"] is not None and out["load1"] > \
            budget["load_per_core"] * out["cores"]:
        out["ok"] = False
        out["reason"] = (f"load {out['load1']:.1f} over "
                         f"{out['cores']} cores — user is "
                         f"busy, cycle skipped")
        return out
    if used / 1e6 > budget["storage_cap_mb"]:
        out["ok"] = False
        out["reason"] = (f"storage cap: dwell store holds "
                         f"{out['used_mb']} MB of "
                         f"{budget['storage_cap_mb']} MB — "
                         f"prune before more grabs")
        return out
    return out


def prune_to_cap(dwell_dir, cap_mb,
                 recordings_dir=RECORDINGS_DIR):
    """Oldest-first eviction across the dwell store and the
    recordings until the pair fit the cap. Returns bytes
    freed."""
    def oldest_files():
        paths = []
        for base in (dwell_dir, recordings_dir):
            if not os.path.isdir(base):
                continue
            for root, _dirs, files in os.walk(base):
                for name in files:
                    p = os.path.join(root, name)
                    if p.endswith((".jsonl", ".json")):
                        continue  # records are not payload
                    try:
                        paths.append((os.path.getmtime(p), p))
                    except OSError:
                        pass
        return sorted(paths)

    freed = 0
    total = dir_bytes(dwell_dir) + dir_bytes(recordings_dir)
    for _mtime, p in oldest_files():
        if total / 1e6 <= cap_mb:
            break
        try:
            size = os.path.getsize(p)
            os.remove(p)
            total -= size
            freed += size
        except OSError:
            pass
    return freed
