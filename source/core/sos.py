"""The SOS minimum as its own running logic (Zak,
2026-11-18): a resident script the WATCHDOG updates,
which fires the SOS itself — so the call for help does
not depend on the watchdog being able to send it.

The contract:
  * the watchdog records the machine's state (mode, the
    failed state in plain words, what realignment needs)
    into sos.json every cycle;
  * the SOS resident reads that log and fires when the
    machine is in limp mode — immediately on the episode,
    then again on an escalation cadence while the fix
    request is IGNORED (still limp);
  * if the watchdog ever can't update — its log goes
    stale — the resident fires anyway, backed by the most
    recent failed state in the log, and names the silence
    itself as the failure;
  * every SOS carries the failed state and its needs for
    realignment. A failure is a communication, in usable
    form, or it is a second failure on top of the first.
"""
import json
import os
import time

STORE_DIR = os.path.join(os.path.expanduser("~"),
                         ".cache", "ai-core", "dwell")
STATE_FILE = os.path.join(STORE_DIR, "sos.json")
ESCALATE_S = 1800          # re-fire while a fix is ignored
LOOP_S = 45                # the resident's own cadence


def needs_for(why):
    """What realignment needs, from the failed state."""
    w = (why or "").lower()
    if "not answering" in w:
        return ("the model service running again — restart "
                "Ollama (sudo systemctl restart ollama) or "
                "run the update (sudo ai-core-update)")
    if "shelf is empty" in w:
        return ("a model on the shelf — pull the paired "
                "model (ollama pull <model>) or run the "
                "update (sudo ai-core-update)")
    if "does not fit" in w:
        return ("memory freed, or a smaller model seated — "
                "the app advises the smallest fitting model "
                "on its Conduit page")
    if "watchdog" in w:
        return ("the watchdog resident alive again — "
                "restart the dwell service")
    return ("a hard reset, or the update "
            "(sudo ai-core-update)")


def _mutate(fn):
    os.makedirs(STORE_DIR, exist_ok=True)
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
    except (OSError, ValueError):
        state = {}
    fn(state)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=1, sort_keys=True)
    os.replace(tmp, STATE_FILE)
    return state


def load():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def record(mode, why, now=None):
    """The watchdog's write: current mode, the failed
    state, and its realignment needs. Opens an episode on
    entering limp; closes it on recovery."""
    now = now or time.time()

    def fn(st):
        prev_why = st.get("why", "")
        st["mode"] = mode
        st["why"] = why
        st["needs"] = needs_for(why) if mode == "limp" else ""
        st["updated_at"] = now
        if mode == "limp":
            if not st.get("episode_since"):
                st["episode_since"] = now
                st["sos_count"] = 0
                st["last_fired"] = 0
        else:
            if st.get("episode_since"):
                st["last_episode"] = {
                    "since": st["episode_since"],
                    "closed": now, "why": prev_why}
            st["episode_since"] = None
    return _mutate(fn)


def stale_after(dwell_s):
    return max(180.0, 3 * float(dwell_s or 60) + 60)


def evaluate(state, now, dwell_s=60):
    """Pure: what should fire right now, from the log.
    Returns a list of {kind, failed_state, needs} — kind is
    'limp' (first fire), 'ignored' (fix request ignored,
    still limp past the escalation window), or
    'watchdog_silent' (the watchdog can't update)."""
    out = []
    updated = state.get("updated_at") or 0
    last_fired = state.get("last_fired") or 0
    if updated and now - updated > stale_after(dwell_s):
        if now - last_fired >= ESCALATE_S:
            out.append({
                "kind": "watchdog_silent",
                "failed_state": (
                    f"the watchdog has not updated its log "
                    f"for {int((now - updated) // 60)} "
                    f"minutes; last recorded state: "
                    f"{state.get('mode', 'unknown')} — "
                    f"{state.get('why', '')}".strip()),
                "needs": needs_for("watchdog")})
        return out
    if state.get("mode") == "limp":
        if not state.get("sos_count"):
            out.append({"kind": "limp",
                        "failed_state": state.get("why", ""),
                        "needs": state.get("needs", "")})
        elif now - last_fired >= ESCALATE_S:
            out.append({"kind": "ignored",
                        "failed_state": state.get("why", ""),
                        "needs": state.get("needs", "")})
    return out


def compose(host, state, fire):
    age = ""
    since = state.get("episode_since")
    if since:
        age = f" (down {int((time.time() - since) // 60)} min)"
    head = {"limp": "🆘 AI Core SOS",
            "ignored": "🆘 AI Core SOS — fix request ignored",
            "watchdog_silent":
                "🆘 AI Core SOS — watchdog silent"}[fire["kind"]]
    lines = [f"{head} on {host}{age}.",
             f"Failed state: {fire['failed_state']}",
             f"Needs for realignment: {fire['needs']}",
             "Senses, dwell and the script floor (web "
             "search + status) are the standing floor while "
             "this lasts."]
    if fire["kind"] == "ignored":
        lines.append(f"SOS count this episode: "
                     f"{(state.get('sos_count') or 0) + 1}. "
                     f"It repeats while the failure is "
                     f"ignored.")
    return "\n".join(lines)


def mark_fired(ok, why, now=None):
    now = now or time.time()

    def fn(st):
        st["last_fired"] = now
        st["sos_count"] = (st.get("sos_count") or 0) + 1
        st["last_attempt"] = {"ok": bool(ok), "why": why,
                              "at": now}
    return _mutate(fn)


def heartbeat(now=None):
    now = now or time.time()
    return _mutate(lambda st: st.update(
        {"resident_seen": now}))
