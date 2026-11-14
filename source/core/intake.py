"""Joy Calculator engine — where the relationship begins.

The Joy Calculator calculates the STARTING DEPTH of the relationship
between a person and the AI side. It is not a form and it does not add
up anything about money or work.

The instrument: paced pages. An introduction, then two groups of
"explainer" pages — Introduction explainers and Use Commitment
explainers. Each explainer is ONE simple statement. The person answers
Agree or Disagree. Each statement explains a use commitment, and the
agree/disagree pattern sets how deep the relationship BEGINS.

The output: a beginning-depth level (see DEPTH_LEVELS), what that
depth means the AI side starts as, and the doctrine line — where it
goes from the beginning is told by time, not by this calculator.

⚠ ALL WORDING IS DRAFT ⚠ — every statement, level name, meaning line,
and the doctrine line below are drafts in Zak's plain register,
written for his red pen. Do not treat any of it as final copy.

Progressive engagement (unchanged mechanic): answers do not wait for
a submit button. The moment an answer is given, EngagementWriter
streams it to the memory ring service (rings/state, port 9108) over
the existing wire protocol — one "set" per answer under
joy:<session>:<sid>, plus a running depth snapshot under
joy:<session>:depth. If the memory service is down, answers queue
locally and drain when it returns; the writer never blocks and never
raises into the UI.

THE DEFAULT MODE. The tab runs in what we call default mode (later
modes hang off this name): the descriptors and button labels nudge —
written to spike curiosity, invitational, never a trap — and every
page carries the same three exits alongside Continue:
  Skip          — pass on one statement; a skip is data too, streamed
                  marked "skipped", and counts as no-signal for depth.
  End           — stop now; the summary reads the partial pattern and
                  says plainly that a partial read is a shallower read.
  Finish later  — a progress marker (joy:<session>:progress, mirrored
                  at joy:latest-progress) keeps the person's place;
                  reopening the tab offers Resume or Start over.
"""
import json
import queue
import threading
import time

from core.protocol import SERVICE_PORTS, mcp_call

MEMORY_PORT = SERVICE_PORTS["memory"]
KEY_PREFIX = "joy"

# --- The doctrine line (DRAFT wording) --------------------------------
# Shown verbatim on the summary page. The calculator sets the
# beginning; it does not pretend to set the destination.
TIME_LINE = (
    "This is only where it begins. Where it goes, time tells — it may "
    "stay just a chatbot and a neglected reminder app, or it may end "
    "up hyper processing lives."
)

# --- The depth scale (ALL NAMES + MEANINGS ARE DRAFT WORDING) ---------
# Zak's named poles: shallow = "just a chatbot and neglected reminder
# app"; deep = "hyper processing lives". Three drafted depths sit
# between them. min_percent is the floor of each band, applied to the
# percent of depth points gathered from the statements answered so far.
DEPTH_LEVELS = [
    {
        "level": 1,
        "min_percent": 0,
        "name": "Just a Chatbot",
        "meaning": "The AI side starts as a tool: you talk, it answers. "
                   "Reminders get set — and mostly get neglected.",
    },
    {
        "level": 2,
        "min_percent": 20,
        "name": "A Helper When Asked",
        "meaning": "The AI side starts as help on call: it remembers "
                   "what you ask it to and lends a hand when you come "
                   "to it.",
    },
    {
        "level": 3,
        "min_percent": 40,
        "name": "A Keeper of the Threads",
        "meaning": "The AI side starts keeping track alongside you, "
                   "holding the threads of what matters so less of it "
                   "slips.",
    },
    {
        "level": 4,
        "min_percent": 60,
        "name": "A Companion in the Loop",
        "meaning": "The AI side starts in the loop with you: checking "
                   "in, noticing changes, carrying the thread of your "
                   "days.",
    },
    {
        "level": 5,
        "min_percent": 80,
        "name": "Hyper Processing Lives",
        "meaning": "The AI side starts woven into your life, "
                   "processing alongside you as it happens — not a "
                   "tool you visit, a presence that runs with you.",
    },
]

# --- The statements (ALL WORDING IS DRAFT) -----------------------------
# Two groups, in page order. Each statement is one simple sentence and
# explains one use commitment. Scoring is transparent and one-way:
# each answer earns the statement's depth points for that side —
#   agree_pts:    depth points earned by answering "Agree"
#   disagree_pts: depth points earned by answering "Disagree"
# Most statements open depth when agreed with. A few are closers:
# they state a limit, so it is DISagreeing with them that opens depth,
# and agreeing simply holds the depth where it is (0 points).
STATEMENTS = [
    # -- Introduction explainers: what the AI side is, how this works --
    {"id": "not-just-app", "group": "introduction",
     "text": "This is more than an app. It's the start of a "
             "relationship between you and the AI side.",
     "agree_pts": 3, "disagree_pts": 0},
    {"id": "it-remembers", "group": "introduction",
     "text": "The AI side can remember what you tell it, so you "
             "don't have to keep repeating yourself.",
     "agree_pts": 3, "disagree_pts": 0},
    {"id": "it-reminds", "group": "introduction",
     "text": "It can remind you about the things you tend to neglect.",
     "agree_pts": 2, "disagree_pts": 0},
    {"id": "you-set-depth", "group": "introduction",
     "text": "How deep this goes is up to you. Your answers here set "
             "where it begins.",
     "agree_pts": 2, "disagree_pts": 0},
    {"id": "change-later", "group": "introduction",
     "text": "You can change your mind later. Nothing you answer "
             "here is locked in.",
     "agree_pts": 2, "disagree_pts": 0},
    # -- Use Commitment explainers: what the AI side would do --
    {"id": "check-in", "group": "commitment",
     "text": "I want it to check in with me, not just wait to be "
             "asked.",
     "agree_pts": 3, "disagree_pts": 0},
    {"id": "track-alongside", "group": "commitment",
     "text": "I want it to keep track of my life alongside me.",
     "agree_pts": 3, "disagree_pts": 0},
    {"id": "notice-changes", "group": "commitment",
     "text": "It can notice when something in my day has changed.",
     "agree_pts": 2, "disagree_pts": 0},
    {"id": "speak-up", "group": "commitment",
     "text": "When something matters, it can bring it up on its own.",
     "agree_pts": 2, "disagree_pts": 0},
    {"id": "learn-my-days", "group": "commitment",
     "text": "I want it to learn how my days actually go.",
     "agree_pts": 2, "disagree_pts": 0},
    {"id": "one-job-only", "group": "commitment",
     "text": "I'm setting this up for one job only.",
     "agree_pts": 0, "disagree_pts": 1},
    {"id": "answers-only", "group": "commitment",
     "text": "I only want answers when I ask questions.",
     "agree_pts": 0, "disagree_pts": 1},
    {"id": "stay-background", "group": "commitment",
     "text": "I'd rather it stays in the background and never "
             "speaks first.",
     "agree_pts": 0, "disagree_pts": 1},
]

STATEMENT_BY_ID = {s["id"]: s for s in STATEMENTS}

# --- The page flow ------------------------------------------------------
# intro (read-through) | statement (Agree/Disagree) | summary (end).
# Page copy here is DRAFT wording too.
PAGES = [
    {
        "kind": "intro",
        "id": "welcome",
        "title": "The Joy Calculator",
        "body": "This little calculator doesn't add up your money or "
                "your work. It works out how deep the relationship "
                "with the AI side begins. Read each statement, then "
                "agree or disagree — there are no wrong answers, "
                "nothing is submitted at the end, and every answer is "
                "handed to the back end the moment you give it.",
    },
    *[{"kind": "statement", **s} for s in STATEMENTS
      if s["group"] == "introduction"],
    {
        "kind": "intro",
        "id": "commitments-ahead",
        "title": "The use commitments",
        "body": "Now the use commitments. Each statement below says, "
                "in plain words, one thing the AI side would do. "
                "Agreeing says: yes, start there. Disagreeing says: "
                "not for me, not now.",
    },
    *[{"kind": "statement", **s} for s in STATEMENTS
      if s["group"] == "commitment"],
    {"kind": "summary", "id": "summary"},
]


def statement_points(stmt, answer):
    """Depth points one answer earns on one statement (transparent)."""
    if answer == "Agree":
        return stmt["agree_pts"]
    if answer == "Disagree":
        return stmt["disagree_pts"]
    return 0


def statement_max(stmt):
    """Most depth points one statement can contribute."""
    return max(stmt["agree_pts"], stmt["disagree_pts"])


def depth_level(percent):
    """The DEPTH_LEVELS entry for a 0-100 depth percent."""
    chosen = DEPTH_LEVELS[0]
    for entry in DEPTH_LEVELS:
        if percent >= entry["min_percent"]:
            chosen = entry
    return chosen


def compute_depth(answers):
    """Work out the beginning depth from the answers collected so far.

    Transparent math: each answered statement contributes the depth
    points of the side the person picked; percent is points over the
    most those answered statements could have given. Every
    contribution is listed in `lines`.

    answers: {sid: {"answer": "Agree"|"Disagree", ...}}
    Returns a dict with answered, total, score, max_score, percent,
    level, level_name, meaning, time_line, and display lines.
    """
    lines = []
    score = 0
    answered_max = 0
    for stmt in STATEMENTS:
        got = answers.get(stmt["id"])
        if got is None:
            continue
        answer = got.get("answer")
        pts = statement_points(stmt, answer)
        best = statement_max(stmt)
        score += pts
        answered_max += best
        note = f"+{pts} depth"
        if pts == 0 and best > 0:
            note = "holds the depth (+0)"
        lines.append(f"{answer} — \u201c{stmt['text']}\u201d \u2192 {note}")
    percent = round(100 * score / answered_max) if answered_max else 0
    entry = depth_level(percent)
    return {
        "answered": len(answers),
        "total": len(STATEMENTS),
        "score": score,
        "max_score": answered_max,
        "percent": percent,
        "level": entry["level"],
        "level_name": entry["name"],
        "meaning": entry["meaning"],
        "time_line": TIME_LINE,
        "lines": lines,
    }


# --- Progressive engagement -------------------------------------------

class EngagementWriter:
    """Streams answers to the memory ring service as they are given.

    Fire-and-forget: record() only enqueues. A daemon worker performs
    the wire calls, counts how many answers the back end holds, keeps
    undeliverable answers in a local queue, and retries them until
    they land. on_status(text) fires whenever the picture changes.
    """

    def __init__(self, session_id=None, on_status=None, port=MEMORY_PORT):
        self.session_id = session_id or f"{int(time.time())}-{threading.get_ident() % 100000}"
        self.port = port
        self.on_status = on_status
        self.held = 0            # answers the back end has absorbed
        self._pending = []       # answer items not yet absorbed
        self._depth = None       # latest depth snapshot to sync
        self._lock = threading.Lock()
        self._wake = queue.Queue()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    # -- producer side (UI thread) --
    def record(self, sid, prompt, answer, weight=0, profile=None):
        item = {
            "key": f"{KEY_PREFIX}:{self.session_id}:{sid}",
            "count": True,
            "value": json.dumps({
                "statement": prompt,
                "answer": answer,
                "depth_points": weight,
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }),
        }
        with self._lock:
            self._pending.append(item)
            if profile is not None:
                self._depth = {
                    "key": f"{KEY_PREFIX}:{self.session_id}:depth",
                    "value": json.dumps(profile),
                }
        self._wake.put(True)
        self._emit_status()

    def record_skip(self, sid, prompt, profile=None):
        """Stream a skip: the statement was passed on. Same key shape
        as an answer, answer marked "skipped", zero depth points —
        depth computation never sees it (the client keeps it out of
        the answers dict), so a skip is no-signal, not a shallow vote.
        """
        self.record(sid, prompt, "skipped", weight=0, profile=profile)

    def save_progress(self, page_index, answers, done=False):
        """Persist the finish-later marker: where the person stopped
        and what they'd answered. Written under this session's
        :progress key and mirrored at joy:latest-progress so a fresh
        tab instance can find the newest unfinished run without
        knowing its session id. done=True closes the run (finished or
        abandoned) so it is never offered back.
        """
        value = json.dumps({
            "session": self.session_id,
            "page_index": page_index,
            "answers": {sid: (a.get("answer") if isinstance(a, dict) else a)
                        for sid, a in answers.items()},
            "done": done,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })
        with self._lock:
            for key in (f"{KEY_PREFIX}:{self.session_id}:progress",
                        f"{KEY_PREFIX}:latest-progress"):
                self._pending.append({"key": key, "count": False,
                                      "value": value})
        self._wake.put(True)

    # -- status --
    def pending_count(self):
        with self._lock:
            return len(self._pending)

    def status_text(self):
        pending = self.pending_count()
        text = f"backend: {self.held} answer{'s' if self.held != 1 else ''} held"
        if pending:
            text += f" · {pending} queued locally (memory service offline)"
        return text

    def _emit_status(self):
        if self.on_status:
            try:
                self.on_status(self.status_text())
            except Exception:
                pass

    # -- worker side --
    def _send(self, item):
        resp = mcp_call(self.port, {"action": "set", "key": item["key"],
                                    "value": item["value"]}, timeout=2)
        return resp.get("status") == "ok"

    def _run(self):
        while True:
            try:
                self._wake.get(timeout=2)
            except queue.Empty:
                pass
            # Drain what we can; a failed send stays queued for retry.
            while True:
                with self._lock:
                    item = self._pending[0] if self._pending else None
                if item is None:
                    break
                if self._send(item):
                    with self._lock:
                        self._pending.pop(0)
                        if item.get("count", True):
                            self.held += 1
                    if item.get("count", True):
                        self._emit_status()
                else:
                    break  # service down; wait for the next wake/timeout
            with self._lock:
                depth = self._depth
            if depth is not None:
                if self._send(depth):
                    with self._lock:
                        if self._depth is depth:
                            self._depth = None


def find_unfinished(port=MEMORY_PORT):
    """Look for an unfinished Joy Calculator run to offer back.

    Reads the joy:latest-progress marker from the memory service.
    Returns {"session", "page_index", "answers"} for the newest
    unfinished run, or None when there is none, it is finished, or
    the memory service can't be reached. v1-simple by design: one
    marker, no new storage system.
    """
    resp = mcp_call(port, {"action": "get",
                           "key": f"{KEY_PREFIX}:latest-progress"},
                    timeout=2)
    raw = resp.get("value")
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if data.get("done") or not data.get("session"):
        return None
    return {
        "session": data["session"],
        "page_index": int(data.get("page_index", 0)),
        "answers": data.get("answers", {}),
    }
