#!/usr/bin/env python3
"""websearch.py — the low tier's free-tier web leg (2026-11-17, Zak's catch).

A low tier is not a handicap. With internet reach, a small local model
plus a deterministic search script plus full system state is genuinely
competent: the knowledge lives on the web, not in the weights. This
script is that leg — free, no API key, no model in the loop: it asks
DuckDuckGo's lite endpoint, and it EXPLAINS itself every run
(expectation + performance), because a conduit that sets expectations
does not go silent about what a result is worth.

Offline, the same tier answers from stored model knowledge and the
system state and metrics it can access — narrower, stated plainly,
still not useless, never zero.

Usage: python3 websearch.py "<question>" [--max N]
Stdlib only.
"""
import html, json, re, sys, time
import urllib.request, urllib.parse

ENDPOINT = "https://lite.duckduckgo.com/lite/?q="

def search(query, max_results=5):
    url = ENDPOINT + urllib.parse.quote_plus(query)
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) ai-core-websearch/0.1"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=20) as r:
        page = r.read().decode("utf-8", "replace")
    fetch_s = time.time() - t0
    results = []
    # DDG lite rows: anchors carrying class='result-link' (attribute order
    # varies — href comes first in the served markup), then snippet cells.
    anchors = re.findall(r"<a[^>]*class='result-link'[^>]*>.*?</a>", page, re.S)
    snippets = re.findall(r"<td class='result-snippet'>(.*?)</td>", page, re.S)
    def clean(s):
        return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()
    for i, a in enumerate(anchors[:max_results]):
        hm = re.search(r"href=\"([^\"]+)\"", a)
        href = hm.group(1) if hm else ""
        m = re.search(r"uddg=([^&]+)", href)
        real = urllib.parse.unquote(m.group(1)) if m else href
        results.append({"title": clean(a), "url": real,
                        "snippet": clean(snippets[i]) if i < len(snippets) else ""})
    return results, round(fetch_s, 2)

def main():
    if len(sys.argv) < 2:
        print("usage: websearch.py \"<question>\" [--max N]")
        return 2
    query = sys.argv[1]
    max_n = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 5
    print(f"EXPLAINER: free-tier web search (DuckDuckGo lite, no key, no model "
          f"in the loop). Expect titles + snippets in seconds — leads at "
          f"network speed, not verified facts; opening a page is the "
          f"verification step. Offline, this tier falls back to stored model "
          f"knowledge + system state, and says so.")
    try:
        results, fetch_s = search(query, max_n)
    except Exception as e:
        print(json.dumps({"ok": False, "query": query,
                          "error": f"web unreachable from this box ({type(e).__name__})",
                          "fallback": "stored model knowledge + system state/metrics only"}))
        return 0
    print(f"PERFORMANCE: fetched in {fetch_s}s, {len(results)} results.")
    print(json.dumps({"ok": True, "query": query, "fetch_s": fetch_s,
                      "results": results}, indent=1))
    return 0

if __name__ == "__main__":
    sys.exit(main())
