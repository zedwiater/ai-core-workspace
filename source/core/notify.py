# --- AI Core module label ---
# Label-Name: notify
# Label-Origin: ai-core-workspace build (Zak/Muse)
# Label-Version: 1
# Label-Does: Telegram alert pipe — reads the user's own bot
#   token from their secrets file, learns the chat from the
#   bot's first incoming message, sends alerts
# --- end label ---
"""Telegram notifications (Zak, 2026-11-18).

The user creates a bot with BotFather and puts its token in
~/.config/ai-core/secrets.json as "telegram-token" — their
file, their credential; this module reads it at send time
and never logs, returns, or stores it anywhere else. A bot
cannot message first: the user sends the bot any message,
and the chat id is learned from that (getUpdates) and saved
back into the same secrets file, other keys untouched.

Everything degrades honestly: no token -> {"ok": False,
"why": "no telegram token yet"}; token but no chat yet ->
the discovery result says so. Sends are plain urllib —
no dependency, no background chatter.
"""
import json
import os
import urllib.parse
import urllib.request

SECRETS = os.path.expanduser("~/.config/ai-core/secrets.json")
API = "https://api.telegram.org/bot{token}/{method}"


def _load_secrets(path=None):
    try:
        with open(path or SECRETS) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_secret(key, value, path=None):
    path = path or SECRETS
    data = _load_secrets(path)
    data[key] = value
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=1)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def token(path=None):
    return _load_secrets(path).get("telegram-token") or None


def chat_id(path=None):
    return _load_secrets(path).get("telegram-chat-id") or None


def _api(method, params, tok, opener=urllib.request.urlopen,
         timeout=10):
    url = API.format(token=tok, method=method)
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data)
    with opener(req, timeout=timeout) as resp:
        return json.load(resp)


def discover_chat_id(path=None, opener=urllib.request.urlopen):
    """Learn the chat from the bot's recent incoming
    messages. Returns the chat id or None."""
    tok = token(path)
    if not tok:
        return None
    try:
        out = _api("getUpdates", {"limit": 20}, tok,
                   opener=opener)
    except Exception:
        return None
    found = None
    for upd in out.get("result", []):
        msg = upd.get("message") or upd.get("edited_message") \
            or {}
        chat = msg.get("chat") or {}
        if chat.get("id"):
            found = chat["id"]
    if found is not None:
        _save_secret("telegram-chat-id", found, path)
    return found


def status(path=None, opener=urllib.request.urlopen):
    tok = token(path)
    out = {"token": bool(tok),
           "chat_id": bool(chat_id(path)),
           "bot": None}
    if tok:
        try:
            me = _api("getMe", {}, tok, opener=opener)
            out["bot"] = (me.get("result") or {}).get("username")
        except Exception:
            out["bot"] = None
    return out


def send(text, path=None, opener=urllib.request.urlopen):
    """Send one message. Returns {"ok": bool, "why": str} —
    the token itself is never in the result."""
    tok = token(path)
    if not tok:
        return {"ok": False,
                "why": "no telegram token yet — create a bot "
                       "with BotFather and put its token in "
                       "~/.config/ai-core/secrets.json as "
                       "\"telegram-token\""}
    cid = chat_id(path)
    if cid is None:
        cid = discover_chat_id(path, opener=opener)
    if cid is None:
        return {"ok": False,
                "why": "the bot has no chat yet — send the "
                       "bot any message first, so it learns "
                       "where to write"}
    try:
        out = _api("sendMessage",
                   {"chat_id": cid, "text": text}, tok,
                   opener=opener)
        return {"ok": bool(out.get("ok")),
                "why": "" if out.get("ok") else str(out)[:120]}
    except Exception as e:
        return {"ok": False, "why": f"send failed: {e}"}
