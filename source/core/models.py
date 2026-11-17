"""Model stacks — models accepted from any angle, in ordered stacks.

Each slot (chat / reason / summarizer) carries a STACK of entries,
not a single model name. An entry is one of:

    {"kind": "ollama", "model": "<name>"}
        a local Ollama model (the angle this app was born on)
    {"kind": "openai", "model": "<name>", "base_url": "<url>",
     "api_key": "<optional>"}
        any OpenAI-compatible endpoint — a neighbor machine's router,
        a free-tier cloud, a paid one. The ring does not care which
        side of the wall the model lives on; the cloud policy does.

Stacks persist through the memory ring service under
app:model-stacks (the app's existing pattern). The chat slot is
served by the first entry that is both reachable and allowed by the
cloud policy (core.settings, group "cloud"):

  never    — non-local entries never answer; local or silence.
  draft    — non-local entries may answer; their plain-text answers
             are labeled as cloud drafts (tool tokens pass through
             unlabeled — tools execute locally either way).
  allowed  — non-local entries answer as themselves.

Every resolution returns a per-entry report saying exactly what was
tried and why each entry was or wasn't served — a dead provider
degrades to the next plug, on the record, never a silent swap.

Only the chat slot has a caller today. Reason and summarizer stacks
are real configuration — displayed, ordered, persisted, probed —
and this module will not pretend anything calls them yet.

All network access goes through one opener so tests can drive every
path headlessly.
"""
import json
import urllib.request

from core.protocol import SERVICE_PORTS, mcp_call

MEMORY_PORT = SERVICE_PORTS["memory"]
STACKS_KEY = "app:model-stacks"
OLLAMA_URL = "http://localhost:11434"

SLOTS = ("chat", "reason", "summarizer")
SLOT_TITLES = {
    "chat": "Chat — the conversational mind",
    "reason": "Reason — the deep tier (no caller yet)",
    "summarizer": "Summarizer — the inflow manager (no caller yet)",
}


def _opener(method, url, payload=None, timeout=5, headers=None):
    """One HTTP round-trip -> (status_code, parsed_json).

    Raises on transport failure; callers translate that into an
    honest 'unreachable' instead of letting it escape.
    """
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode())


def human_error(e):
    """Translate a transport/model failure into guidance a person can
    act on. A raw exception string in the chat is a design failure:
    the user should learn what is down, why it matters, and the exact
    remedy — the technical tail rides along in parentheses, demoted,
    never deleted."""
    import urllib.error
    tail = f"({type(e).__name__}: {e})"
    if isinstance(e, urllib.error.HTTPError) and e.code == 404:
        return ("That model isn't on this machine yet — the door answered, "
                "but the model hasn't been pulled. Pull it with: "
                "ollama pull <model> — then ask me again. " + tail)
    if isinstance(e, urllib.error.URLError) and \
            ("111" in str(e) or "refused" in str(e).lower()):
        return ("I can't reach Ollama at localhost:11434 — the model door "
                "isn't answering, so there's no brain on the other end yet. "
                "Start it with: sudo systemctl enable --now ollama — then "
                "confirm the model is pulled: ollama list. " + tail)
    if isinstance(e, (TimeoutError,)) or "timed out" in str(e).lower():
        return ("The model took longer than the patience setting allows. "
                "It may still be loading its seat — give it a moment, or "
                "raise patience in Options. " + tail)
    return f"Something failed on the way to the model. {tail}"


def entry_label(entry):
    if entry.get("kind") == "openai":
        return f"endpoint · {entry.get('model', '?')} @ {entry.get('base_url', '?')}"
    return f"ollama · {entry.get('model', '?')}"


def is_local(entry):
    return entry.get("kind") == "ollama"


def _sanitize_entry(entry):
    if not isinstance(entry, dict):
        return None
    kind = entry.get("kind")
    model = entry.get("model")
    if kind not in ("ollama", "openai") or not isinstance(model, str) \
            or not model:
        return None
    clean = {"kind": kind, "model": model}
    if kind == "openai":
        base = entry.get("base_url")
        if not isinstance(base, str) or not base:
            return None
        clean["base_url"] = base.rstrip("/")
        if isinstance(entry.get("api_key"), str) and entry["api_key"]:
            clean["api_key"] = entry["api_key"]
    return clean


def default_stacks(config_model):
    """A fresh stack set: the configured Ollama model serves chat;
    reason and summarizer start honestly empty."""
    return {
        "chat": [{"kind": "ollama", "model": config_model}],
        "reason": [],
        "summarizer": [],
    }


def _merge_stacks(raw, config_model):
    stacks = default_stacks(config_model)
    if not raw:
        return stacks
    try:
        stored = json.loads(raw)
    except (TypeError, ValueError):
        return stacks
    if not isinstance(stored, dict):
        return stacks
    for slot in SLOTS:
        entries = stored.get(slot)
        if isinstance(entries, list):
            clean = [e for e in (_sanitize_entry(x) for x in entries)
                     if e is not None]
            stacks[slot] = clean
    return stacks


def load_stacks(config_model, call=None, port=MEMORY_PORT):
    call = call or mcp_call
    resp = call(port, {"action": "get", "key": STACKS_KEY}, timeout=2)
    return _merge_stacks(resp.get("value"), config_model)


def save_stacks(stacks, call=None, port=MEMORY_PORT):
    call = call or mcp_call
    resp = call(port, {"action": "set", "key": STACKS_KEY,
                       "value": json.dumps(stacks)}, timeout=2)
    return resp.get("status") == "ok"


def discover_ollama(opener=None, base_url=OLLAMA_URL, timeout=3):
    """Model names the local Ollama reports, [] when it's silent."""
    opener = opener or _opener
    try:
        _code, data = opener("GET", f"{base_url}/api/tags",
                             timeout=timeout)
        return [m["name"] for m in data.get("models", [])
                if isinstance(m, dict) and "name" in m]
    except Exception:
        return []


def probe_entry(entry, opener=None, timeout=3):
    """Ask one entry whether it can serve. Returns a report dict:
    {"state": "reachable"|"model-missing"|"unreachable",
     "detail": one honest line}. Never raises."""
    opener = opener or _opener
    try:
        if entry.get("kind") == "ollama":
            _code, data = opener("GET", f"{OLLAMA_URL}/api/tags",
                                 timeout=timeout)
            names = [m.get("name") for m in data.get("models", [])]
            if entry["model"] in names:
                return {"state": "reachable",
                        "detail": "Ollama has this model loaded"}
            return {"state": "model-missing",
                    "detail": "Ollama is up but doesn't list this model"}
        headers = {}
        if entry.get("api_key"):
            headers["Authorization"] = f"Bearer {entry['api_key']}"
        code, _data = opener("GET", f"{entry['base_url']}/models",
                             timeout=timeout, headers=headers)
        if 200 <= code < 300:
            return {"state": "reachable",
                    "detail": "endpoint answered its /models list"}
        return {"state": "unreachable",
                "detail": f"endpoint answered HTTP {code}"}
    except Exception as e:
        return {"state": "unreachable", "detail": f"no answer ({e})"}


def resolve_chat_entry(stacks, policy="draft", budget_ok=True,
                       opener=None, timeout=3):
    """Pick who serves chat: the first reachable, policy-allowed
    entry in the chat stack, top first.

    Returns (entry_or_None, report) where report is a list of
    (entry, verdict) in stack order — verdicts: "served",
    "unreachable", "model-missing", "blocked by cloud policy",
    "blocked by session budget". The caller surfaces the report;
    nothing is swapped silently.
    """
    report = []
    for entry in stacks.get("chat", []):
        if not is_local(entry):
            if policy == "never":
                report.append((entry, "blocked by cloud policy"))
                continue
            if not budget_ok:
                report.append((entry, "blocked by session budget"))
                continue
        probe = probe_entry(entry, opener=opener, timeout=timeout)
        if probe["state"] == "reachable":
            report.append((entry, "served"))
            return entry, report
        report.append((entry, probe["state"]))
    return None, report


def chat_completion(entry, messages, timeout=30, opener=None):
    """One chat round-trip against one entry -> stripped text.

    Raises RuntimeError with an honest message on any failure; the
    tool loop already knows how to surface those.
    """
    opener = opener or _opener
    try:
        if entry.get("kind") == "ollama":
            _code, data = opener(
                "POST", f"{OLLAMA_URL}/api/chat",
                payload={"model": entry["model"],
                         "messages": messages, "stream": False},
                timeout=timeout)
            return data.get("message", {}).get("content", "").strip()
        headers = {}
        if entry.get("api_key"):
            headers["Authorization"] = f"Bearer {entry['api_key']}"
        _code, data = opener(
            "POST", f"{entry['base_url']}/chat/completions",
            payload={"model": entry["model"], "messages": messages},
            timeout=timeout, headers=headers)
    except Exception as e:
        raise RuntimeError(
            f"{entry_label(entry)} didn't answer: {e}") from e
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("endpoint answered with no choices")
    return choices[0].get("message", {}).get("content", "").strip()
