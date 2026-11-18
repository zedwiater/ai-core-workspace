#!/usr/bin/env python3
"""report.py — the failure report (Zak's telemetry ask, 2026-11-17,
built to his house rule: nothing phones home).

Running it builds ONE redacted markdown file —
~/ai-core-failure-report.md — and prints a prefilled GitHub issue
link. The user reads the file, opens the link, and presses submit
themselves, under their own account. Nothing is sent by the tool,
no credential is needed or stored, and redaction (home path,
username, hostname) happens before anything is written.

What it carries: the shape of the machine (the saved crawl
receipt: threads, RAM, GPU, the pairing), the state of the
services and the model door, and the last journal lines of the
door — the evidence a failure actually leaves behind.
"""
import json
import os
import platform
import re
import subprocess
import sys
import urllib.parse
import urllib.request

ISSUES_URL = "https://github.com/zedwiater/ai-core-workspace/issues/new"
UNITS = ["ollama"] + [f"ai-mcp-{n}" for n in
                      ("files", "web", "vision", "shell", "sound",
                       "voice", "coding", "memory")]


def redact(text, user=None, host=None, home=None):
    user = user if user is not None else os.environ.get("USER", "")
    host = host if host is not None else platform.node()
    home = home if home is not None else os.path.expanduser("~")
    out = text
    if home and home != "~":
        out = out.replace(home, "~")
    if user:
        out = re.sub(rf"(?<![\w-]){re.escape(user)}(?![\w-])", "<user>", out)
    if host:
        out = out.replace(host, "<host>")
    return out


def _run(cmd, timeout=6):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout)
        return (r.stdout or "") + (r.stderr or "")
    except Exception:
        return ""


def collect():
    data = {"platform": platform.platform(),
            "python": platform.python_version()}
    crawl_path = "/opt/ai-core/crawl/expectations.json"
    try:
        c = json.load(open(crawl_path))
        data["crawl"] = {
            "threads": c["cpu"]["effective_threads"],
            "ram_gb": round(c["ram"]["effective_mb"] / 1024, 1),
            "gpus": [f"{g.get('vendor', '?')} {g.get('vram_gb', 0)}GB"
                     for g in c.get("gpus", [])],
            "pairing": c.get("pairing"),
            "budget": c["expectations"]["budget"]
                      ["max_parallel_model_tasks"]}
    except Exception:
        data["crawl"] = None
    data["services"] = {}
    for u in UNITS:
        state = _run(["systemctl", "is-active", f"{u}.service"]).strip()
        data["services"][u] = state.splitlines()[0] if state else "unknown"
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags",
                                    timeout=2) as r:
            tags = json.loads(r.read().decode())
        data["door"] = [m["name"] for m in tags.get("models", [])]
    except Exception:
        data["door"] = None
    data["journal_ollama"] = _run(
        ["journalctl", "-u", "ollama", "-n", "15", "--no-pager"]).strip()
    data["coredump"] = _run(
        ["coredumpctl", "list", "--no-pager", "-q"]).strip()[-1500:]
    return data


def render(data):
    lines = ["# AI Core failure report", ""]
    lines.append(f"- Platform: {data.get('platform')}")
    lines.append(f"- Python: {data.get('python')}")
    c = data.get("crawl")
    if c:
        lines.append(f"- Machine: {c['threads']} effective threads, "
                     f"{c['ram_gb']} GB RAM, GPUs: "
                     f"{', '.join(c['gpus']) or 'none'}, "
                     f"budget {c['budget']}")
        if c.get("pairing"):
            p = c["pairing"]
            lines.append(f"- Pairing: {p['model']} — {p['mode']} "
                         f"(GPU layers {p['gpu_layers']}/"
                         f"{p['total_layers']})")
    else:
        lines.append("- Machine: no saved crawl receipt found")
    lines.append("")
    lines.append("## Services")
    for u, s in (data.get("services") or {}).items():
        lines.append(f"- {u}: {s}")
    lines.append("")
    lines.append("## Model door")
    lines.append(f"- {'answering: ' + ', '.join(data['door']) if data.get('door') is not None else 'SILENT'}")
    lines.append("")
    lines.append("## Ollama journal (last lines)")
    lines.append("```")
    lines.append(data.get("journal_ollama") or "(unavailable)")
    lines.append("```")
    if data.get("coredump"):
        lines.append("")
        lines.append("## Recent coredumps")
        lines.append("```")
        lines.append(data["coredump"])
        lines.append("```")
    return "\n".join(lines) + "\n"


def main():
    out = os.path.expanduser("~/ai-core-failure-report.md")
    if "--out" in sys.argv:
        out = sys.argv[sys.argv.index("--out") + 1]
    text = redact(render(collect()))
    with open(out, "w") as f:
        f.write(text)
    print(f"Report written: {out}")
    print("Nothing has been sent. Read it, then open this link and "
          "press submit yourself if it looks right:")
    body = text if len(text) <= 6000 else text[:6000] + "\n[truncated — attach the full file]\n"
    q = urllib.parse.urlencode(
        {"title": "Failure report", "body": body})
    print(f"{ISSUES_URL}?{q}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
