#!/usr/bin/env python3
"""conduit_pages.py — the Conduit surface of the desktop client.

Zak's mandate (2026-11-17): after crawl and install, the user is
greeted with information and a map and options — not a blank chat.
These pages are that greeting, built from the same core modules the
installer runs (core.census, core.pipes): the landing page IS the
crawl, rendered.

Pages: Conduit (landing, simple view first), Joy Gradient, Nodes,
Dwell, Roam Watch, Help & Support. The chat remains — as one door
among them, no longer the whole house.

Design rules carried from the refinement:
- Data layer is headless (no gi imports at module level) and unit
  tested; widget builders import Gtk/Adw locally.
- Every panel states what it found and what it did NOT find. An
  absent sibling node, an absent social digest, an unpulled model —
  each is said plainly, with the remedy, never papered over.
- Nothing here starts services, pulls models, or changes the system.
  The pages inform and offer; acting stays with the user.
"""
import glob, json, os, platform, shutil, sys, time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core import census as census_mod
from core import pipes as pipes_mod

STATE_DIR = os.path.expanduser("~/.config/ai-core")
CONDUIT_JSON = os.path.join(STATE_DIR, "conduit.json")
NODE_DIRS = [os.path.join(STATE_DIR, "nodes"),
             os.path.expanduser("~/ai-core/nodes"),
             os.path.expanduser("~/ai-core-edge/state")]

# ---------------------------------------------------------------- data

def crawl_now():
    """Run the same crawl the installer runs; return the assembled
    census + pipes picture for this machine."""
    c = {"host": platform.node(),
         "os": f"{platform.system()} {platform.release()}",
         "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
         "cpu": census_mod.cpu_probe(), "ram": census_mod.ram_probe(),
         "gpus": census_mod.gpu_probe(),
         "disk_free_gb": round(shutil.disk_usage(os.path.expanduser("~")).free / 1e9),
         "runtimes": census_mod.runtime_probe()}
    c["expectations"] = census_mod.build(c)
    ctx = {"ports": pipes_mod.listening_ports(),
           "relay_paths": pipes_mod.mediamtx_paths()}
    found, missing, feeds = [], [], set()
    for entry in pipes_mod.REGISTRY:
        ok = pipes_mod.detect(entry, ctx)
        row = {"id": entry["id"], "name": entry["name"], "kind": entry["kind"],
               "found": ok, "feeds_plugin": entry["feeds"],
               "lane": pipes_mod.lane_for(entry, ok)}
        (found if ok else missing).append(row)
        if ok:
            feeds.add(entry["feeds"])
    offers = [o for o in pipes_mod.SCRIPT_TIER_OFFERS
              if all(n in feeds for n in o["needs"])]
    return {"census": c,
            "pipes_found": found,
            "pipes_not_found": [m["id"] for m in missing],
            "script_tier_offers": offers}

def tier_map(crawl):
    return {t["tier"]: t for t in crawl["census"]["expectations"]["tiers"]}

def greeting_lines(crawl):
    """The simple-view greeting: plain words, this machine's truth."""
    c = crawl["census"]
    tiers = tier_map(crawl)
    budget = c["expectations"]["budget"]
    lines = [f"Welcome — this is {c['host']} ({c['os']}).",
             f"I crawled your hardware before greeting you: "
             f"{c['cpu']['effective_threads']} effective threads, "
             f"{round(c['ram']['effective_mb'] / 1024, 1)} GB of usable RAM, "
             f"{'a GPU (' + ', '.join(g['name'] for g in c['gpus']) + ')' if c['gpus'] else 'no GPU — models take CPU seats here'}, "
             f"{c['disk_free_gb']} GB of free disk.",
             f"Working budget: {budget['max_parallel_model_tasks']} model task(s) at once. "
             f"Script tasks are never seat-bound — the floor is always up."]
    conv = tiers.get("conversation", {})
    lines.append(f"Conversation: {conv.get('status', 'unknown')} — "
                 f"{conv.get('expectation') or conv.get('announcement', '')}")
    know = tiers.get("knowledge (web)", {})
    if know:
        lines.append(f"Knowledge: {know.get('status', '')}.")
    lines.append("Ask me anything in the AI Core tab. The tabs beside it are your "
                 "system, drawn from this same crawl: Joy Gradient (how patient to "
                 "be), Nodes (your other machines), Dwell (what I notice over time), "
                 "Roam Watch (new arrivals and services), Help & Support.")
    return lines

def expectation_table_text(crawl):
    c = crawl["census"]
    out = [f"Expectation table — {c['host']} ({c['ts']})",
           f"CPU: {c['cpu']['logical_threads']} logical / {c['cpu']['effective_threads']} "
           f"effective threads ({c['cpu']['effective_source']}); load {c['cpu']['load1']}",
           f"RAM: {c['ram']['effective_mb']} MB effective ({c['ram']['effective_source']}); "
           f"disk free {c['disk_free_gb']} GB", ""]
    for t in c["expectations"]["tiers"]:
        exp = t.get("expectation") or t.get("announcement", "")
        if t.get("latency"):
            exp = f"{t['latency']}. {exp}"
        out.append(f"• {t['tier']}: {t['status']} — {exp}")
    out += ["", "Figures are estimates calibrated on the reference install and "
            "labeled as such. A seat is announced before it is taken; a silent "
            "hang is a bug, never a state."]
    return "\n".join(out)

def pipes_table_text(crawl):
    out = ["Pipes recognized on this machine (feed → plugin, lane):"]
    for p in crawl["pipes_found"]:
        out.append(f"• {p['name']} [{p['id']}] → {p['feeds_plugin']} — lane {p['lane']}")
    if crawl["script_tier_offers"]:
        out.append("")
        out.append("Script tiers these feeds make possible:")
        for o in crawl["script_tier_offers"]:
            out.append(f"• {o['offer']} — {o['basis']}")
    if crawl["pipes_not_found"]:
        out += ["", "Not found (and therefore not promised): "
                + ", ".join(crawl["pipes_not_found"])]
    return "\n".join(out)

# ------------------------------------------------------------- comfort

GRADIENTS = [
    {"id": "quick", "name": "Quick — smallest resident",
     "promise": "The smallest model stays resident: first words in about a "
                "second, short answers, no seat changes. Depth is traded "
                "away on purpose."},
    {"id": "balanced", "name": "Balanced — ok with some delay",
     "promise": "A mid-size resident for conversation; deeper work takes an "
                "announced seat while you watch progress. The reference "
                "install runs here."},
    {"id": "deep", "name": "Deep — announced, streamed, minutes",
     "promise": "The biggest seat the hardware fits, loaded on announcement "
                "with progress streamed. Slowest greetings, deepest work."},
]

def load_comfort():
    try:
        with open(CONDUIT_JSON) as f:
            return json.load(f).get("comfort", "balanced")
    except Exception:
        return "balanced"

def save_comfort(value):
    os.makedirs(STATE_DIR, exist_ok=True)
    data = {}
    if os.path.exists(CONDUIT_JSON):
        try:
            data = json.load(open(CONDUIT_JSON))
        except Exception:
            data = {}
    data["comfort"] = value
    with open(CONDUIT_JSON, "w") as f:
        json.dump(data, f, indent=1)
    return value

# ------------------------------------------------------- nodes / files

def find_node_reports():
    """Sibling edge reports, wherever the user keeps them. Each report
    is one node's snap report (edge_report.py output)."""
    reports = []
    for d in NODE_DIRS:
        for p in sorted(glob.glob(os.path.join(d, "**", "report.json"),
                                  recursive=True)):
            try:
                r = json.load(open(p))
                r["_path"] = p
                reports.append(r)
            except Exception:
                pass
    return reports

def find_social():
    for d in NODE_DIRS + [os.path.expanduser("~/ai-core")]:
        for p in glob.glob(os.path.join(d, "**", "SOCIAL.md"), recursive=True):
            try:
                return open(p).read(), p
            except Exception:
                pass
    return None, None

def find_watch():
    pats = [os.path.expanduser("~/ai-core-edge/state/hub_watch.json"),
            os.path.join(STATE_DIR, "hub_watch.json"),
            os.path.expanduser("~/ai-core/conduit/state/hub_watch.json")]
    for p in pats:
        if os.path.exists(p):
            try:
                return json.load(open(p)), p
            except Exception:
                pass
    return None, None

def nodes_text(crawl, reports):
    c = crawl["census"]
    out = [f"This node: {c['host']} ({platform.machine()}) — "
           f"{c['expectations']['budget']['max_parallel_model_tasks']} model task(s), "
           f"{len(crawl['pipes_found'])} pipes recognized.", ""]
    if reports:
        out.append("Sibling nodes reporting to this conduit:")
        for r in reports:
            out.append(f"• {r.get('node')} ({r.get('arch')}) — roles: "
                       f"{', '.join(r.get('roles', []))}; budget "
                       f"{r.get('budget', {}).get('max_parallel_model_tasks', '?')}; "
                       f"reported {r.get('ts')} ({r.get('_path')})")
    else:
        out.append("No sibling nodes have reported yet. To add one: install "
                   "this same app on the other machine (or copy the edge kit "
                   "from source/core + source/core/edge), run edge_report.py "
                   "there, and place its report.json under "
                   "~/.config/ai-core/nodes/<name>/ — it will appear here, "
                   "and the conduit will advise it in the hourly social.")
    return "\n".join(out)

def dwell_text(social, social_path, crawl):
    out = ["Dwell is how this system learns your rhythms: a resident observer "
           "notices, a gatekeeper brain vetoes noise, and what survives becomes "
           "the journal — receipts first, narrative second. The nodes hold an "
           "hourly five-minute social: system, connections, stability, "
           "progress.", ""]
    if social:
        out.append(f"Latest node social ({social_path}):")
        out.append(social)
    else:
        out.append("No node social has been recorded on this machine yet. It "
                   "arrives when at least one node reports and the conduit "
                   "renders its digest (node_social.py) — until then this page "
                   "says so, rather than performing a social that never met.")
    return "\n".join(out)

def watch_text(watch, watch_path):
    out = ["Roam Watch is the hub's active crawl: hourly, it diffs ports, "
           "devices and services against the last crawl and suggests how "
           "each new arrival should integrate — a plugged-in camera, new "
           "software, a Frigate-class service. Credential pointers name "
           "where a login lives (your password manager); the hub never "
           "stores the secret.", ""]
    if watch:
        out.append(f"Latest watch — {watch.get('node')} at {watch.get('ts')} "
                   f"({watch_path}):")
        for s in watch.get("suggestions", []):
            out.append(f"• [{s.get('kind')}] {s.get('service')}: {s.get('status')}")
            out.append(f"    role: {s.get('role')} · feeds: {s.get('feeds')}")
            for o in s.get("linking_options", []):
                out.append(f"    – {o.get('option')}: {o.get('target')}")
        if not watch.get("suggestions"):
            out.append("• No new arrivals since the baseline crawl.")
    else:
        out.append("No watch has run on this machine yet. Start one with "
                   "hub_watch.py from the edge kit — the first run sets the "
                   "baseline, later runs diff against it.")
    return "\n".join(out)

# ---------------------------------------------------------------- help

FAQ = [
    ("What am I looking at?",
     "The Conduit landing. On launch the app crawls your hardware and greets "
     "you with what it found: your budget, your tiers and their promises, "
     "your pipes. Simple view first; Advanced unfolds the full tables."),
    ("Why did it say 'connection refused' (older versions)?",
     "The model door (Ollama, localhost:11434) wasn't answering — the brain "
     "wasn't home. Current builds translate that into the remedy: start the "
     "service (sudo systemctl enable --now ollama), then check the model is "
     "pulled (ollama list / ollama pull <model>)."),
    ("What is a tier?",
     "A class of work with its own promise: conversation, deep, vision, "
     "image, audio, knowledge, script floor. Each degrades along its own "
     "ladder and says so — never silently, never to zero."),
    ("What is a seat?",
     "A model's place in memory and CPU/GPU while it works. Seats are "
     "announced before they're taken; the conversation seat is pinned so a "
     "chat is never evicted by a specialist organ taking its own seat."),
    ("What are the comfort modes (Joy Gradient)?",
     "Quick: smallest resident, ~1s to first word. Balanced: mid resident, "
     "deep work on announced seats. Deep: biggest seat, streamed progress, "
     "minutes. Pick in the Joy Gradient tab; the expectations on the "
     "landing page are written for the mode you chose."),
    ("What are the view modes?",
     "Simple shows the greeting, your options, and plain-language status. "
     "Advanced adds the full expectation table, pipe lanes and budget "
     "basis. Custom (in the full hub) toggles panels individually."),
    ("What are the autonomy modes?",
     "No access: the app is an observer — it reports states and metrics "
     "from public probes, touches nothing. Full access: it finds organs "
     "(cameras, mics, services), dwells and logs from grab to release, and "
     "its receipts are always available. You grant and revoke; the app "
     "states which mode it is in."),
    ("How do other machines join (Nodes)?",
     "Same DNA, subdivided: the edge kit runs the same crawl on a Pi or a "
     "spare laptop and files one report. The conduit reads all reports, "
     "advises each node, and places work where the headroom is."),
    ("What is dwell / the node social?",
     "Dwell is the system's slow attention: noticed moments, gated by a "
     "small brain, journaled with receipts. Hourly, the nodes hold a "
     "five-minute social — system, connections, stability, progress — "
     "rendered in the Dwell tab."),
    ("A new device appeared in Roam Watch — what now?",
     "The hub identified it and proposed an integration: what feed it "
     "joins, what lane it takes, how to link it (web UI card, credential "
     "pointer, feed hookup). Nothing integrates without your go-ahead."),
    ("Use case: the basement",
     "A mic + camera node with a wake word: 'hi' engages the quick router "
     "(show a camera, grab the last five minutes), the full wake word "
     "engages conversation. Speech answers in the room; the roam patrols "
     "the cameras as the single live feed while audio stays parallel for "
     "the lock phrase and emergencies."),
    ("Use case: a weak laptop",
     "Low tier is a tier, not a handicap: a small resident model, the "
     "script floor for commands, and the web leg for knowledge. Fully "
     "offline it narrows to stored knowledge + system state — and says so."),
    ("Use case: a house of Pis",
     "Each Pi runs the edge kit inside its headroom: sensing and reporting "
     "on the small nodes, compute placed on the strongest, the conduit "
     "keeping the map and the advice flowing both ways."),
]

HELP_INTRO = ("Help & Support — FAQ, explainers, use cases, modes.\n"
              "Search filters the FAQ by meaning, not just letters: try "
              "'slow', 'refused', 'pi', 'private', 'seat'.\n")

SYNONYMS = {"slow": "patience timeout seat deep", "fast": "quick resident",
            "refused": "connection ollama door start", "broken": "error refused door",
            "pi": "nodes edge raspberry sibling", "privacy": "autonomy access observer",
            "camera": "roam watch vision pipe", "offline": "web knowledge low tier"}

def faq_filter(query):
    q = (query or "").lower().strip()
    if not q:
        return FAQ
    toks = set(q.split())
    for t in list(toks):
        toks.update(SYNONYMS.get(t, "").split())
    return [(a, b) for a, b in FAQ
            if toks & set((a + " " + b).lower().split())]

# ------------------------------------------------------------- widgets
# Gtk/Adw are imported inside the builders: the data layer above must
# stay importable (and testable) on a machine with no display at all.

def _text_view():
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    tv = Gtk.TextView()
    tv.set_editable(False)
    tv.set_cursor_visible(False)
    tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
    tv.set_left_margin(12)
    tv.set_right_margin(12)
    tv.set_top_margin(10)
    tv.set_bottom_margin(10)
    sw = Gtk.ScrolledWindow()
    sw.set_vexpand(True)
    sw.set_child(tv)
    return sw, tv.get_buffer()

def collect_state():
    """Everything the pages render, gathered off the UI thread."""
    social, social_path = find_social()
    watch, watch_path = find_watch()
    return {"crawl": crawl_now(), "reports": find_node_reports(),
            "social": social, "social_path": social_path,
            "watch": watch, "watch_path": watch_path}

def attach(notebook, on_model_choice=None):
    """Build the Conduit pages into the client's notebook and start
    the crawl. Returns a dict of populate callbacks (already wired);
    the landing page is inserted first and selected. When
    on_model_choice is given, the model-advice popup is shown after
    the crawl: keep-current or pull-the-fit, the user's call."""
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Gtk, GLib
    import threading

    populates = {}

    # --- Conduit (landing): simple view first, Advanced unfolds ---
    home_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    greet_sw, greet_buf = _text_view()
    adv_sw, adv_buf = _text_view()
    adv_sw.set_visible(False)
    toggle = Gtk.ToggleButton(label="Advanced view — full tables")
    toggle.connect("toggled", lambda b: adv_sw.set_visible(b.get_active()))
    home_box.append(greet_sw)
    home_box.append(toggle)
    home_box.append(adv_sw)

    def pop_home(state):
        crawl = state["crawl"]
        text = "\n\n".join(greeting_lines(crawl))
        if state.get("advice"):
            text += "\n\n" + state["advice"]["message"]
        greet_buf.set_text(text)
        adv_buf.set_text(expectation_table_text(crawl) + "\n\n"
                         + pipes_table_text(crawl))
    populates["home"] = pop_home

    # --- Joy Gradient ---
    joy_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    joy_box.set_margin_start(14)
    joy_box.set_margin_end(14)
    joy_box.set_margin_top(12)
    joy_title = Gtk.Label(label="How patient should this system be?")
    joy_title.set_xalign(0)
    joy_box.append(joy_title)
    joy_status = Gtk.Label(label="")
    joy_status.set_xalign(0)
    joy_status.set_wrap(True)
    group = None
    buttons = {}
    for g in GRADIENTS:
        b = Gtk.CheckButton(label=g["name"])
        if group is not None:
            b.set_group(group)
        else:
            group = b
        b._gradient = g
        buttons[g["id"]] = b
        joy_box.append(b)
        p = Gtk.Label(label=g["promise"])
        p.set_xalign(0)
        p.set_wrap(True)
        p.set_margin_start(24)
        joy_box.append(p)

        def on_pick(btn, g=g):
            if btn.get_active():
                save_comfort(g["id"])
                joy_status.set_text(f"Standing choice: {g['name']}. "
                                    "Expectations are written for this mode.")
        b.connect("toggled", on_pick)
    joy_box.append(joy_status)
    joy_sw = Gtk.ScrolledWindow()
    joy_sw.set_vexpand(True)
    joy_sw.set_child(joy_box)

    def pop_joy(state):
        cur = load_comfort()
        if cur in buttons:
            buttons[cur].set_active(True)
        joy_status.set_text(f"Standing choice: "
                            f"{next(g['name'] for g in GRADIENTS if g['id'] == cur)}.")
    populates["joy"] = pop_joy

    # --- Nodes / Dwell / Roam Watch: text pages ---
    nodes_sw, nodes_buf = _text_view()
    dwell_sw, dwell_buf = _text_view()
    watch_sw, watch_buf = _text_view()
    populates["nodes"] = lambda s: nodes_buf.set_text(
        nodes_text(s["crawl"], s["reports"]))
    populates["dwell"] = lambda s: dwell_buf.set_text(
        dwell_text(s["social"], s["social_path"], s["crawl"]))
    populates["watch"] = lambda s: watch_buf.set_text(
        watch_text(s["watch"], s["watch_path"]))

    # --- Help & Support ---
    help_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    search = Gtk.SearchEntry()
    search.set_placeholder_text("Search the FAQ — try 'slow', 'refused', 'pi', 'seat'…")
    faq_sw, faq_buf = _text_view()

    def render_faq(items):
        faq_buf.set_text(HELP_INTRO + "\n" + "\n\n".join(
            f"Q: {q}\nA: {a}" for q, a in items))
    render_faq(FAQ)
    search.connect("search-changed",
                   lambda e: render_faq(faq_filter(e.get_text())))
    help_box.append(search)
    help_box.append(faq_sw)
    populates["help"] = lambda s: None

    pages = [("Conduit", home_box), ("Joy Gradient", joy_sw),
             ("Nodes", nodes_sw), ("Dwell", dwell_sw),
             ("Roam Watch", watch_sw), ("Help & Support", help_box)]
    for i, (title, widget) in enumerate(pages):
        if i == 0:
            notebook.insert_page(widget, Gtk.Label(label=title), 0)
        else:
            notebook.append_page(widget, Gtk.Label(label=title))
    notebook.set_current_page(0)

    def work():
        try:
            state = collect_state()
        except Exception as e:  # the landing must never take the app down
            state = None
            GLib.idle_add(greet_buf.set_text,
                          "The crawl failed on this machine "
                          f"({type(e).__name__}: {e}). The chat and the other "
                          "doors still work; the crawl's own scripts "
                          "(source/core/census.py, pipes.py) can be run by "
                          "hand to see the underlying error.")
        if state is not None:
            try:
                state["advice"] = model_advice(state["crawl"], fetch_tags())
            except Exception:
                state["advice"] = None
            for fn in populates.values():
                GLib.idle_add(fn, state)
            if on_model_choice is not None and state.get("advice") \
                    and state["advice"]["state"] in ("keep", "upgrade", "none"):
                GLib.idle_add(_show_model_dialog, notebook,
                              state["advice"], on_model_choice)
    threading.Thread(target=work, daemon=True).start()
    return populates

# ---------------------------------------------------------- model advice
# Zak's rule (2026-11-17): check if other models exist first. If they
# do, the app ADVISES — keep the current model, or take the better
# fit — in a popup the user decides on. Never a silent pull, never a
# silent overwrite of a shelf someone built on purpose.

import re, subprocess, urllib.request

def _params_b(name):
    m = re.search(r"(\d+(?:\.\d+)?)\s*b\b", (name or "").lower())
    if m:
        return float(m.group(1))
    m = re.search(r"-(\d+(?:\.\d+)?)$", (name or "").lower())
    return float(m.group(1)) if m else None

def fitted_model(ram_mb):
    """The installer's fit rule, mirrored so the popup and the
    installer never give different advice on the same machine."""
    if (ram_mb or 0) >= 16 * 1024:
        return "qwen3.5:9b", 9.0
    return "qwen3:8b", 8.0

def fetch_tags():
    """The door's shelf, or None if the door isn't answering."""
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags",
                                    timeout=2.5) as r:
            return json.load(r).get("models", [])
    except Exception:
        return None

def model_advice(crawl, tags):
    ram = crawl["census"]["ram"]["effective_mb"]
    fitted, fitted_p = fitted_model(ram)
    if tags is None:
        return {"state": "door-silent", "fitted": fitted,
                "message": "The model door (Ollama, localhost:11434) isn't "
                           "answering, so there is no shelf to advise on. "
                           "Start it with: sudo systemctl enable --now ollama "
                           "— then this advice runs again on next launch."}
    names = [m.get("name", "") for m in tags if m.get("name")]
    if not names:
        return {"state": "none", "fitted": fitted,
                "message": f"No models are pulled on this machine yet. The "
                           f"fit for your hardware is {fitted}. Pull it now, "
                           "or later from the Models tab — nothing was pulled "
                           "without asking."}
    sized = sorted(names, key=lambda n: _params_b(n) or 0, reverse=True)
    resident = sized[0]
    resident_p = _params_b(resident) or 0
    if resident_p >= fitted_p:
        return {"state": "keep", "resident": resident, "fitted": fitted,
                "message": f"You already have {resident} on this machine — "
                           f"it meets or beats the fitted model for your "
                           f"hardware ({fitted}). Advice: keep your current "
                           "model. Nothing was pulled, nothing was changed."}
    return {"state": "upgrade", "resident": resident, "fitted": fitted,
            "message": f"Your largest resident model is {resident}; the fit "
                       f"for your hardware is {fitted}. You can pull the "
                       "better fit now (it downloads in the background and "
                       "your current model keeps working), or keep what you "
                       "have — the choice is yours, and nothing happens "
                       "without it."}

def _show_model_dialog(notebook, advice, on_choice):
    """The popup itself. Returns False (landing text carries the
    advice instead) if the dialog can't be shown on this Gtk."""
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    state = advice["state"]
    if state == "keep":
        labels = [f"Keep {advice['resident']}", "Not now"]
    elif state == "upgrade":
        labels = [f"Pull {advice['fitted']}", f"Keep {advice['resident']}",
                  "Not now"]
    elif state == "none":
        labels = [f"Pull {advice['fitted']}", "Not now"]
    else:
        return False
    try:
        dlg = Gtk.AlertDialog()
        dlg.set_message("Your models, your call")
        dlg.set_detail(advice["message"])
        dlg.set_buttons(labels)

        def done(d, result):
            try:
                idx = d.choose_finish(result)
            except Exception:
                return
            label = labels[idx] if 0 <= idx < len(labels) else ""
            if label.startswith("Keep "):
                on_choice(advice["resident"])
            elif label.startswith("Pull "):
                log = os.path.join(STATE_DIR, "pull.log")
                os.makedirs(STATE_DIR, exist_ok=True)
                with open(log, "ab") as lf:
                    subprocess.Popen(["ollama", "pull", advice["fitted"]],
                                     stdout=lf, stderr=lf)
        dlg.choose(notebook.get_root(), None, done)
        return True
    except Exception:
        return False
