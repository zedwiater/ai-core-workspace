# --- AI Core service label ---
# Label-Name: web
# Label-Origin: ai-core-workspace build (Zak/Muse)
# Label-Version: 1
# Label-Does: web fetch/search and page-health checks
# --- end label ---
#!/usr/bin/env python3
"""George's MCP Web Service — fetch URLs + extract text via TCP

Ring: atmosphere (outer ring — world-facing, takes the weather).
Runs the shared ring lifecycle: register -> serve -> report health.

Note: this service's "health" action predates the ring convention —
it probes internet reachability and keeps that meaning. The scaffold
therefore does not override it; this service's transductive health is
its "ping" plus the reachability probe.
"""
import html.parser
import os
import sys
import urllib.request

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from core.ring_service import serve

PORT = 9102


class TextExtractor(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
    def handle_data(self, data):
        t = data.strip()
        if t: self.text.append(t)


def ping(req):
    return {"status": "pong"}


def fetch(req):
    url = req.get("url", "")
    r = urllib.request.urlopen(url, timeout=10)
    raw = r.read().decode(errors='replace')
    return {"status": "ok", "content": raw[:5000], "code": r.status}


def extract(req):
    url = req.get("url", "")
    r = urllib.request.urlopen(url, timeout=10)
    raw = r.read().decode(errors='replace')
    ex = TextExtractor(); ex.feed(raw)
    return {"status": "ok", "content": " ".join(ex.text)[:5000], "code": r.status}


def health(req):
    r = urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=5)
    return {"status": "ok", "reachable": r.status == 200, "code": r.status}


if __name__ == "__main__":
    serve("web", "atmosphere", PORT,
          {"ping": ping, "fetch": fetch, "extract": extract, "health": health},
          unknown_fmt="Unknown: {action}")
