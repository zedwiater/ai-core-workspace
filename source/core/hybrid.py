"""Hybrid — parent, daughter, and both on one box.

The Sensor Ego pattern at skeleton scale, honestly labeled: this
is briefs + a hash-linked receipt chain + real transport + real
queueing. It is NOT the full Sensor Ego v3 — no graded-consensus
dialogue, no subconscious pass. That stack is a named expansion
path (see docs/APP_EXPERIENCE_AND_HARNESS.md, "Parent, daughter,
hybrid").

DAUGHTER: keeps a hash-linked chain of its dwell briefs
(seq, ts, prev-hash — sha256 over the canonical body), and on each
beat emits a sized BRIEF — floor summary + chain head, descriptors
and briefs only, never raw audio/video (there is no path in this
module that could carry any) — to its parent's endpoint over the
existing wire protocol: a memory `set` under daughter:<id>:brief.
Unreachable parent → briefs queue locally and drain, in order, on
reconnect (the EngagementWriter pattern, on disk).

PARENT: the ingest surface is the memory service itself — briefs
land as keys. read_daughters() scans them back, verifies each
brief against the daughter's chain head it carries, checks the
pairing secret, and ages every brief against the stale threshold.

PAIRING: a shared secret generated on one box and carried by the
owner to the other (Setup door). Briefs carry it; the parent marks
briefs whose secret matches "verified" and all others "unverified"
— the wire itself has no auth in v1, and this module says so
rather than dressing the token up as transport security.

HYBRID: role "hybrid" runs both halves against the box's own
memory service — the self-test configuration the tests exercise.
"""
import hashlib
import json
import os
import time
from pathlib import Path

from core.protocol import SERVICE_PORTS, mcp_call

MEMORY_PORT = SERVICE_PORTS["memory"]
BRIEF_PREFIX = "daughter:"
GENESIS = "0" * 64


# --- The chain -----------------------------------------------------------

def canonical(body):
    return json.dumps(body, sort_keys=True, separators=(",", ":"))


def chain_hash(prev, body):
    return hashlib.sha256(
        (prev + canonical(body)).encode()).hexdigest()


def chain_append(chain, body):
    """Append one entry: {seq, ts, body, prev, hash}. Pure — the
    caller owns persistence."""
    prev = chain[-1]["hash"] if chain else GENESIS
    entry = {"seq": len(chain) + 1, "ts": body.get("ts", ""),
             "body": body, "prev": prev}
    entry["hash"] = chain_hash(prev, body)
    return entry


def verify_chain(chain):
    """(True, None) when every link checks; (False, seq) at the
    first broken one."""
    prev = GENESIS
    for i, entry in enumerate(chain):
        if entry.get("seq") != i + 1 or entry.get("prev") != prev:
            return False, entry.get("seq", i + 1)
        if entry.get("hash") != chain_hash(prev, entry["body"]):
            return False, entry["seq"]
        prev = entry["hash"]
    return True, None


class ChainStore:
    """The daughter's chain, on disk as one JSON list. Small by
    design — a brief per dwell beat."""

    def __init__(self, path):
        self.path = Path(path)
        self.chain = []
        if self.path.exists():
            try:
                self.chain = json.loads(self.path.read_text())
            except (ValueError, OSError):
                self.chain = []

    def append(self, body):
        entry = chain_append(self.chain, body)
        self.chain.append(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.chain))
        os.replace(tmp, self.path)
        return entry

    def head(self):
        return self.chain[-1]["hash"] if self.chain else GENESIS


# --- Briefs ----------------------------------------------------------------

def build_brief(daughter_id, snapshot, pair_secret=None):
    """A sized brief from the daughter's latest floor snapshot:
    alignment + who's up/down + process count when the floor
    recorded one. Nothing else leaves the daughter."""
    body = {
        "daughter": daughter_id,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "floor": None,
    }
    if snapshot:
        body["floor"] = {
            "aligned": snapshot.get("aligned"),
            "up": snapshot.get("up"),
            "down": snapshot.get("down"),
            "mismatches": len(snapshot.get("mismatches", [])),
            "beat": snapshot.get("beat"),
            "processes": snapshot.get("processes"),
        }
    if pair_secret:
        body["pair"] = pair_secret
    return body


class BriefQueue:
    """On-disk outbox: briefs that couldn't reach the parent,
    drained in order when it answers again."""

    def __init__(self, path):
        self.path = Path(path)

    def _load(self):
        if not self.path.exists():
            return []
        try:
            return [json.loads(ln) for ln in
                    self.path.read_text().splitlines() if ln.strip()]
        except (ValueError, OSError):
            return []

    def _save(self, items):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text("".join(json.dumps(i) + "\n" for i in items))
        os.replace(tmp, self.path)

    def enqueue(self, payload):
        items = self._load()
        items.append(payload)
        self._save(items)

    def pending(self):
        return len(self._load())

    def drain(self, send):
        """Try the queue in order; stop at the first failure.
        Returns how many landed."""
        items = self._load()
        sent = 0
        for payload in items:
            if send(payload):
                sent += 1
            else:
                break
        if sent:
            self._save(items[sent:])
        return sent


class DaughterRuntime:
    """The daughter half, driven by the floor's beats (the client
    calls beat() from the floor companion — wake and dwell only,
    never mid-conversation)."""

    def __init__(self, daughter_id, chain_store, queue, parent_host,
                 parent_port=MEMORY_PORT, pair_secret=None, call=None):
        self.daughter_id = daughter_id
        self.store = chain_store
        self.queue = queue
        self.parent_host = parent_host
        self.parent_port = parent_port
        self.pair_secret = pair_secret
        self._call = call or mcp_call
        self.last_result = None

    def _send(self, payload):
        resp = self._call(self.parent_port, payload,
                          host=self.parent_host, timeout=3)
        return resp.get("status") == "ok"

    def beat(self, snapshot):
        """One dwell/wake beat: brief → chain → try the parent;
        queue on failure, drain what was waiting first."""
        drained = self.queue.drain(self._send)
        body = build_brief(self.daughter_id, snapshot,
                           pair_secret=self.pair_secret)
        entry = self.store.append(body)
        payload = {"action": "set",
                   "key": f"{BRIEF_PREFIX}{self.daughter_id}:brief",
                   "value": json.dumps({"entry": entry})}
        sent = self._send(payload)
        if not sent:
            self.queue.enqueue(payload)
        self.last_result = {
            "seq": entry["seq"], "hash": entry["hash"],
            "sent": sent, "drained": drained,
            "queued": self.queue.pending(),
        }
        return self.last_result


# --- The parent's side -------------------------------------------------------

def read_daughters(call=None, port=MEMORY_PORT, host="127.0.0.1",
                   pair_secret=None, stale_minutes=45, now=None):
    """Scan the memory service for daughter briefs and grade them:
    {id: {brief, entry, age_s, stale, verified, chain_ok}}.

    chain_ok verifies the brief's own carried entry hash (the full
    chain lives on the daughter; the head + linkage is what a brief
    can honestly prove from here)."""
    call = call or mcp_call
    now = now if now is not None else time.time()
    out = {}
    resp = call(port, {"action": "list"}, host=host, timeout=3)
    keys = [e["key"] for e in resp.get("entries", [])
            if e.get("key", "").startswith(BRIEF_PREFIX)
            and e.get("key", "").endswith(":brief")]
    for key in keys:
        daughter_id = key[len(BRIEF_PREFIX):-len(":brief")]
        got = call(port, {"action": "get", "key": key},
                   host=host, timeout=3)
        try:
            data = json.loads(got.get("value") or "{}")
            entry = data["entry"]
            body = entry["body"]
        except (ValueError, KeyError, TypeError):
            continue
        try:
            ts = time.mktime(time.strptime(
                body["ts"], "%Y-%m-%dT%H:%M:%S"))
            age = max(0.0, now - ts)
        except (ValueError, KeyError):
            age = None
        out[daughter_id] = {
            "brief": body,
            "entry": entry,
            "age_s": age,
            "stale": age is None or age > stale_minutes * 60,
            "verified": bool(pair_secret)
            and body.get("pair") == pair_secret,
            "chain_ok": entry.get("hash") == chain_hash(
                entry.get("prev", GENESIS), body),
        }
    return out


def daughters_floor_probe(call=None, port=MEMORY_PORT,
                          pair_secret=None, stale_minutes=45):
    """What the parent's floor snapshot carries about its
    daughters: last brief age + staleness per daughter. Returns {}
    when there are none or memory is silent."""
    try:
        daughters = read_daughters(call=call, port=port,
                                   pair_secret=pair_secret,
                                   stale_minutes=stale_minutes)
    except Exception:
        return {}
    return {did: {"age_s": d["age_s"], "stale": d["stale"],
                  "verified": d["verified"],
                  "chain_ok": d["chain_ok"],
                  "head": d["entry"]["hash"][:12]}
            for did, d in daughters.items()}


def default_state_dir():
    return Path.home() / ".config" / "ai-core"
