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


def discover_sizes(opener=None, base_url=OLLAMA_URL, timeout=3):
    """{model name: size GB} from /api/tags; {} when silent."""
    opener = opener or _opener
    try:
        _code, data = opener("GET", f"{base_url}/api/tags",
                             timeout=timeout)
        return {m["name"]: round(m.get("size", 0) / (1024 ** 3), 2)
                for m in data.get("models", [])
                if isinstance(m, dict) and "name" in m}
    except Exception:
        return {}


def fit_check(size_gb, avail_gb):
    """Can this machine seat a model of size_gb right now?

    Returns (ok, line). The need is the weights x 1.3 — KV cache
    and runtime ride on top — and a refusal names the arithmetic.
    On 2026-11-17 an unguarded 8B seat on a 7.6 GB laptop (3.1 GB
    free, no swap) got the whole Ollama service OOM-killed by the
    kernel; the app must refuse that seat before the kernel has
    to. Never raises.
    """
    need = size_gb * 1.3
    if need <= avail_gb:
        return True, (f"fits — needs ~{need:.1f} GB of the "
                      f"{avail_gb:.1f} GB free")
    return False, (f"needs ~{need:.1f} GB free (weights "
                   f"{size_gb:.1f} GB + cache and runtime) but only "
                   f"{avail_gb:.1f} GB is free — seating it would "
                   f"get Ollama killed by the kernel")


def mem_available_gb(path="/proc/meminfo"):
    """Free-memory truth for fit decisions; 0.0 when unreadable."""
    try:
        with open(path) as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / (1024 * 1024)
    except (OSError, ValueError, IndexError):
        pass
    return 0.0


def mem_total_gb(path="/proc/meminfo"):
    """Total RAM; 0.0 when unreadable."""
    try:
        with open(path) as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / (1024 * 1024)
    except (OSError, ValueError, IndexError):
        pass
    return 0.0


# The OS and desktop keep this much, whatever else is running —
# the same reserve the pairing uses (core/pairing.py).
OS_RESERVE_GB = 2.0


def machine_fit(size_gb, total_gb):
    """Can this MACHINE hold a model of size_gb — the pairing's
    question, asked against total RAM minus the OS reserve.
    Returns (ok, line).

    Distinct from fit_check (this MOMENT's free memory) on
    purpose: on 2026-11-18 the app's own paired voice was
    refused a seat because a browser had eaten the momentary
    free memory, and the picker branded it 'won't fit here' —
    while the same model had seated fine an hour earlier. A
    model that fits the machine gets its seat ATTEMPT; only a
    model that can never fit the machine is refused outright
    (the 8B-on-7.6 GB case this guard exists for)."""
    need = size_gb * 1.3
    usable = total_gb - OS_RESERVE_GB
    if need <= usable:
        return True, (f"fits this machine — needs ~{need:.1f} GB "
                      f"of its {usable:.1f} GB usable")
    return False, (f"too big for this machine — needs "
                   f"~{need:.1f} GB (weights {size_gb:.1f} GB + "
                   f"cache and runtime) but the machine has "
                   f"{usable:.1f} GB usable after the OS reserve")


def pick_default_model(available, sizes, total_gb, stack_top=None):
    """The app's default voice (Zak, 2026-11-18): the app sets
    ITSELF as the default — ai-core-talking, the model it built
    for this machine — then the stack's standing top, then the
    largest model that FITS THE MACHINE (machine_fit: total RAM
    minus the OS reserve, never the moment's free memory —
    a busy desktop must not dethrone the paired voice). Falls
    back to the talking model even unfit (its seat refusal
    explains the arithmetic) and finally to the first model."""
    if not available:
        return None

    def fits(name):
        s = sizes.get(name)
        return s is not None and machine_fit(s, total_gb)[0]

    for name in available:
        if name.split(":")[0] == "ai-core-talking" and fits(name):
            return name
    if stack_top and stack_top in available and fits(stack_top):
        return stack_top
    fitting = [n for n in available if fits(n)]
    if fitting:
        return max(fitting, key=lambda n: sizes.get(n, 0))
    for name in available:
        if name.split(":")[0] == "ai-core-talking":
            return name
    return available[0]


def model_label(name, sizes, total_gb):
    """What the picker shows — SHORT, because a dropdown entry
    sets the window's minimum width (2026-11-18: the long
    verdict form stretched the whole window). Whose voice and
    how big; the fit story lives in the seat state beside the
    picker and in the Models tab, not in the entry text."""
    bits = []
    if name.split(":")[0] == "ai-core-talking":
        bits.append("app voice")
    size = sizes.get(name)
    if size:
        bits.append(f"{size:.1f} GB")
    return name + (" · " + " · ".join(bits) if bits else "")


def seat_model(model, opener=None, keep_alive="30m", timeout=180):
    """Actually load a model into Ollama, then PROVE the seat via
    /api/ps. Returns (ok, line); never raises. Selecting a model
    in the app must seat it — a shelf listing is not a seat
    (Zak's play-session finding, 2026-11-17: ollama ps sat empty
    while the app ran)."""
    opener = opener or _opener
    try:
        opener("POST", f"{OLLAMA_URL}/api/generate",
               payload={"model": model, "prompt": "",
                        "keep_alive": keep_alive, "stream": False},
               timeout=timeout)
    except Exception as e:
        return False, f"{model} could not be seated: {e}"
    try:
        _code, data = opener("GET", f"{OLLAMA_URL}/api/ps", timeout=5)
        for m in data.get("models", []):
            if m.get("name") == model:
                gb = round(m.get("size", 0) / (1024 ** 3), 1)
                where = m.get("details", {}).get("family", "model")
                return True, (f"Seated: {model} resident in Ollama "
                              f"({gb} GB, {where})")
    except Exception as e:
        return False, (f"{model} was asked to seat but the proof "
                       f"read failed: {e}")
    return False, (f"{model} was asked to seat but does not appear "
                   f"in ollama ps — not seated")


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
