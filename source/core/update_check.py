"""Update awareness (Zak, 2026-11-18: 'is there not a way to
update the app automatically?').

Two halves: a daily systemd timer runs ai-core-update (which
pulls and re-installs only when the source moved), and the
app itself checks on launch — reading the install stamp the
installer leaves in ~/.config/ai-core/installed.json — and
offers the update in its header when one is waiting. This
module is the check; it never updates anything itself.
"""
import json
import os
import subprocess

STAMP = os.path.expanduser("~/.config/ai-core/installed.json")


def read_stamp(path=None):
    try:
        with open(path or STAMP) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def commits_behind(src, runner=subprocess.run):
    """How many upstream commits the checkout is behind, or
    None when git cannot say. Fetches quietly first."""
    try:
        runner(["git", "-c", f"safe.directory={src}", "-C", src,
                "fetch", "--quiet"],
               capture_output=True, timeout=30)
        r = runner(["git", "-c", f"safe.directory={src}", "-C",
                    src, "rev-list", "--count", "HEAD..@{u}"],
                   capture_output=True, text=True, timeout=15)
        return int((r.stdout or "0").strip())
    except Exception:
        return None


def check(path=None, runner=subprocess.run):
    """{state: current|behind|unknown, behind, commit, src}."""
    stamp = read_stamp(path)
    if not stamp or not stamp.get("src") \
            or not os.path.isdir(stamp["src"]):
        return {"state": "unknown"}
    behind = commits_behind(stamp["src"], runner)
    if behind is None:
        return {"state": "unknown", **stamp}
    return {"state": "behind" if behind else "current",
            "behind": behind, **stamp}
