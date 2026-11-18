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
import glob, json, os, platform, shutil, subprocess, sys, time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core import census as census_mod
from core import pairing as pairing_mod
from core import pipes as pipes_mod
from core import agreement as agreement_mod

_MODEL_POPUP_SHOWN = False

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
         "cameras": census_mod.camera_probe(),
         "audio": census_mod.audio_probe(),
         "reach": census_mod.reach_probe(),
         "disk_free_gb": round(shutil.disk_usage(os.path.expanduser("~")).free / 1e9),
         "runtimes": census_mod.runtime_probe()}
    c["expectations"] = census_mod.build(c)
    try:
        c["pairing"] = pairing_mod.pair(c)
    except Exception:
        pass
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
             f"{'a GPU (' + ', '.join(g.get('name') or (g.get('vendor', 'GPU') + ' GPU') for g in c['gpus']) + ')' if c['gpus'] else 'no GPU — models take CPU seats here'}, "
             f"{c['disk_free_gb']} GB of free disk"
             f"{', and a camera (' + ', '.join(cam.get('name', cam.get('device', 'camera')) for cam in c.get('cameras', [])) + ')' if c.get('cameras') else ''}"
             f"{', and a microphone (' + next(a['name'] for a in c.get('audio', []) if a.get('capture')) + ')' if any(a.get('capture') for a in c.get('audio', [])) else ''}.",
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
    try:
        p = pairing_mod.pair(c)
        layers = (f", {p['gpu_layers']}/{p['total_layers']} layers on the GPU"
                  if p["gpu_layers"] is not None else "")
        out.append(f"Pairing (fresh shelf): {p['model']} — {p['mode']}{layers}. "
                   f"{p['tier_basis']}.")
        out.append("")
    except Exception:
        pass
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
                "second, short answers, no seat changes. Chat patience is "
                "30 seconds — a slow answer is cut short, never a long wait. "
                "Depth is traded away on purpose."},
    {"id": "balanced", "name": "Balanced — ok with some delay",
     "promise": "A mid-size resident for conversation; deeper work takes an "
                "announced seat while you watch progress. Chat patience is "
                "1 minute. The reference install runs here."},
    {"id": "deep", "name": "Deep — announced, streamed, minutes",
     "promise": "The biggest seat the hardware fits, loaded on announcement "
                "with progress streamed. Chat patience is 5 minutes — long "
                "answers finish. Slowest greetings, deepest work."},
]

def load_comfort():
    return _load_conduit_json().get("comfort", "balanced")

def save_comfort(value):
    data = _load_conduit_json()
    data["comfort"] = value
    _save_conduit_json(data)
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

def dwell_text(social, social_path, crawl, reach_enabled=None):
    out = ["Dwell is how this system learns your rhythms: a resident observer "
           "notices, a gatekeeper brain vetoes noise, and what survives becomes "
           "the journal — receipts first, narrative second. The nodes hold an "
           "hourly five-minute social: system, connections, stability, "
           "progress.", ""]
    enabled = reach_enabled or {}
    in_set = [r for r in reach_rows(crawl) if enabled.get(r["id"])]
    out.append("In the hub's dwell/roam set — your switches on the "
               "Nodes page:")
    if in_set:
        for r in in_set:
            out.append(f"• {r['label']} — {r['suggests']}")
    else:
        out.append("  nothing yet — flip a switch on the Nodes page "
                   "to pull a device or pipe into the hub.")
    out.append("")
    if social:
        out.append(f"Latest node social ({social_path}):")
        out.append(social)
    else:
        out.append("No node social has been recorded on this machine yet. It "
                   "arrives when at least one node reports and the conduit "
                   "renders its digest (node_social.py) — until then this page "
                   "says so, rather than performing a social that never met.")
    return "\n".join(out)

def watch_text(watch, watch_path, suggestions_on=True):
    out = ["Roam Watch is the hub's active crawl: hourly, it diffs ports, "
           "devices and services against the last crawl and suggests how "
           "each new arrival should integrate — a plugged-in camera, new "
           "software, a Frigate-class service. Credential pointers name "
           "where a login lives (your password manager); the hub never "
           "stores the secret.", ""]
    if watch:
        out.append(f"Latest watch — {watch.get('node')} at {watch.get('ts')} "
                   f"({watch_path}):")
        if not suggestions_on:
            out.append("• Suggestions are muted by your switch on the "
                       "Conduit tab — the watch still ran; flip it back "
                       "on to see what it found.")
            return "\n".join(out)
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
    ("The installer stopped halfway — is it safe to run again?",
     "Yes. Re-running is the designed recovery: the installer backs up "
     "the previous install first, merges with whatever is already "
     "running (your models, your tuned services), and continues. "
     "Nothing is uninstalled by running it twice."),
    ("How do updates and fixes reach my install?",
     "Run bash update.sh in your checkout: it pulls the latest tree "
     "and re-runs the installer, which merges with your system and "
     "backs up the previous install first — re-running is the patch "
     "path. A full reset is bash install.sh uninstall, then bash "
     "install.sh again."),
    ("Something failed — how do I report it?",
     "Run ai-core-report. It builds one redacted file "
     "(~/ai-core-failure-report.md: machine shape, service states, "
     "door state, journal tails — home path, username and hostname "
     "stripped) and prints a prefilled GitHub issue link. You read "
     "the file and press submit yourself; nothing is ever sent "
     "automatically."),
    ("The app is stuck, stacked, or eating the machine — rescue?",
     "From a text console (Ctrl+Alt+F3, log in): pkill -f "
     "ai-client.py, then rm -f ~/.config/autostart/ai-core.desktop, "
     "then Ctrl+Alt+F1 back. Current builds make stacking "
     "structurally impossible (a one-instance lock, no autostart "
     "by default). The full repairs glossary — every known "
     "failure, its cause, its commands — is docs/REPAIRS.md in "
     "the repo, written for humans and AI alike."),
    ("The kernel terminated the app for low memory — what was that?",
     "The OS protecting itself: the app (in the bad case, several "
     "stacked copies, or a model seated too large for the RAM) "
     "used memory the system needed. Do not press the "
     "notification's Restart button. Current builds reserve "
     "memory for the desktop in the pairing itself and unload "
     "models when idle on small machines. See R4 in "
     "docs/REPAIRS.md."),
    ("The installer says Ollama wasn't there — what happened?",
     "On a machine with no model door, current builds install Ollama "
     "as part of setup, pair a model to your hardware, pull it, and "
     "set its layers. If the door is still silent afterwards, the "
     "landing page states the remedy and the service commands."),
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
    sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    sw.set_propagate_natural_width(False)
    sw.set_propagate_natural_height(False)
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

def load_agreement():
    """The user's standing privilege agreement (core/agreement)."""
    return agreement_mod.load(CONDUIT_JSON)


# ------------------------------------------------- first-run welcome

ABOUT_FIELDS = [
    ("call_name", "What should I call you?"),
    ("working_on", "What are you working on lately?"),
    ("answer_style",
     "How do you like answers — brief, or with the reasoning?"),
]


def load_about():
    return _load_conduit_json().get("about", {})


def save_about_field(key, value):
    data = _load_conduit_json()
    about = data.setdefault("about", {})
    about[key] = value
    _save_conduit_json(data)
    return about


def load_welcomed():
    return bool(_load_conduit_json().get("welcomed"))


def save_welcomed():
    data = _load_conduit_json()
    data["welcomed"] = True
    _save_conduit_json(data)


def attach(notebook, on_model_choice=None, on_comfort=None,
           on_agreement=None, on_welcomed=None):
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

    # Scripts & automation — plain-language switches (Zak's ask).
    opts_title = Gtk.Label(label="Scripts & automation — plain switches")
    opts_title.set_xalign(0)
    opts_title.set_margin_start(12)
    opts_title.set_margin_top(10)
    home_box.append(opts_title)
    current_opts = load_options()
    for opt in SCRIPT_OPTIONS:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.set_margin_start(12)
        row.set_margin_end(12)
        sw = Gtk.Switch()
        sw.set_active(current_opts[opt["key"]])
        sw.set_valign(Gtk.Align.START)
        sw.connect("notify::active",
                   lambda s, _p, k=opt["key"]: save_option(k, s.get_active()))
        texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        lab = Gtk.Label(label=opt["label"])
        lab.set_xalign(0)
        hlp = Gtk.Label(label=opt["help"])
        hlp.set_xalign(0)
        hlp.set_wrap(True)
        texts.append(lab)
        texts.append(hlp)
        row.append(sw)
        row.append(texts)
        home_box.append(row)

    # The privilege agreement — three levels, the user's choice,
    # changeable any time (Zak, 2026-11-18). Default observer:
    # begin as chatbot + search assist, no permissions granted.
    agr_title = Gtk.Label(label="Permissions — what this app "
                                "is allowed to do")
    agr_title.set_xalign(0)
    agr_title.set_margin_start(12)
    agr_title.set_margin_top(14)
    home_box.append(agr_title)
    agr_blurb = Gtk.Label(label="")
    agr_blurb.set_xalign(0)
    agr_blurb.set_wrap(True)
    agr_blurb.set_margin_start(12)
    agr_blurb.set_margin_end(12)
    agr_disc = Gtk.Label(label=agreement_mod.DISCLAIMER)
    agr_disc.set_xalign(0)
    agr_disc.set_wrap(True)
    agr_disc.set_margin_start(12)
    agr_disc.set_margin_end(12)
    current_level = load_agreement()
    agr_group = [None]

    def agr_chosen(btn, level):
        if not btn.get_active():
            return
        agreement_mod.save(CONDUIT_JSON, level)
        lv = next(x for x in agreement_mod.LEVELS
                  if x["id"] == level)
        agr_blurb.set_text(lv["blurb"])
        agr_disc.set_visible(level == "all")
        if on_agreement is not None:
            on_agreement(level)

    agr_btns = []
    for lv in agreement_mod.LEVELS:
        abtn = Gtk.CheckButton(label=lv["name"])
        if agr_group[0] is not None:
            abtn.set_group(agr_group[0])
        else:
            agr_group[0] = abtn
        abtn.set_margin_start(12)
        abtn.set_active(lv["id"] == current_level)
        abtn.connect("toggled", agr_chosen, lv["id"])
        home_box.append(abtn)
        agr_btns.append(abtn)
        if lv["id"] == current_level:
            agr_blurb.set_text(lv["blurb"])
            agr_disc.set_visible(lv["id"] == "all")
    home_box.append(agr_blurb)
    home_box.append(agr_disc)

    # Permissions are the FIRST choice on the page, not the
    # last (Zak, 2026-11-18: he had to dig for the setting).
    # However the widgets were constructed, the visible order
    # is: greeting, permissions, everything else.
    _prev = greet_sw
    for _w in [agr_title] + agr_btns + [agr_blurb, agr_disc]:
        home_box.reorder_child_after(_w, _prev)
        _prev = _w

    # --- First-run welcome: the get-to-know-you card ---
    # Setup must END somewhere (Zak, 2026-11-18: the app kept
    # 'failing on finality of setup'). On a first run this card
    # sits at the very top: three short questions, the
    # permissions choice right below it, and a Done button
    # that closes setup and starts the guided path (blinking
    # tabs) to the chat window. Once welcomed, it never
    # reappears.
    welcome_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                          spacing=6)
    welcome_box.set_margin_start(12)
    welcome_box.set_margin_end(12)
    welcome_box.set_margin_top(10)
    w_title = Gtk.Label(label="Welcome — let's get to know "
                              "one another")
    w_title.set_xalign(0)
    welcome_box.append(w_title)
    w_intro = Gtk.Label(
        label="Three quick things, then pick this app's "
              "permissions right below — Full (All) or None "
              "(Observer). Nothing here locks; everything can "
              "change later.")
    w_intro.set_xalign(0)
    w_intro.set_wrap(True)
    welcome_box.append(w_intro)
    about_saved = load_about()
    about_entries = {}
    for key, question in ABOUT_FIELDS:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                      spacing=8)
        q = Gtk.Label(label=question)
        q.set_xalign(0)
        entry = Gtk.Entry()
        entry.set_text(about_saved.get(key, ""))
        entry.set_hexpand(True)
        entry.connect("activate",
                      lambda e, k=key: save_about_field(
                          k, e.get_text()))
        about_entries[key] = entry
        row.append(q)
        row.append(entry)
        welcome_box.append(row)
    w_done = Gtk.Button(
        label="Done — next: how patient should it be? →")

    def _welcome_done(_b):
        for k, e in about_entries.items():
            save_about_field(k, e.get_text())
        save_welcomed()
        welcome_box.set_visible(False)
        if on_welcomed is not None:
            on_welcomed(load_about())
    w_done.connect("clicked", _welcome_done)
    welcome_box.append(w_done)
    home_box.append(welcome_box)
    home_box.reorder_child_after(welcome_box, None)
    welcome_box.set_visible(not load_welcomed())

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
                if on_comfort is not None:
                    on_comfort(g["id"])
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
    watch_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    links_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    links_box.set_margin_start(12)
    links_box.set_margin_top(8)
    watch_box.append(links_box)
    watch_box.append(watch_sw)

    def pop_watch(state):
        opts = load_options()
        watch_buf.set_text(watch_text(state["watch"], state["watch_path"],
                                      suggestions_on=opts["watch_suggestions"]))
        while (child := links_box.get_first_child()) is not None:
            links_box.remove(child)
        if not opts["service_links"]:
            return
        for link in service_links(state["watch"]):
            btn = Gtk.LinkButton(uri=link["url"],
                                 label=f"Open {link['service']}")
            links_box.append(btn)
    # The Nodes page is also the reach map: below the node text,
    # one switch per organ/pipe the crawl found. A switch is the
    # user's confirmation; on enable it runs the item's
    # connection script when one exists, and the hub's dwell set
    # (the Dwell page) reflects exactly the switched-on rows.
    nodes_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                        spacing=6)
    nodes_box.append(nodes_sw)
    reach_title = Gtk.Label(
        label="This node's reach — pull a device or pipe into "
              "the hub (dwell + roam)")
    reach_title.set_xalign(0)
    reach_title.set_margin_start(12)
    reach_title.set_margin_top(10)
    nodes_box.append(reach_title)
    reach_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                        spacing=4)
    nodes_box.append(reach_box)
    reach_status = Gtk.Label(label="")
    reach_status.set_xalign(0)
    reach_status.set_wrap(True)
    reach_status.set_margin_start(12)
    nodes_box.append(reach_status)
    state_cell = {}

    def on_reach_toggle(sw, _p, row):
        on = sw.get_active()
        save_reach_enabled(row["id"], on)
        if not on:
            reach_status.set_text(
                f"{row['label']} — out of the hub's dwell set.")
        else:
            script = connect_script_for(row["id"])
            if script is None:
                reach_status.set_text(
                    f"✓ {row['label']} is in the hub's dwell/roam "
                    f"set — the hub reads this switch. (No "
                    f"connection script for this item yet.)")
            else:
                reach_status.set_text(
                    f"Running the connection script for "
                    f"{row['label']}…")

                def run_script():
                    try:
                        r = subprocess.run(
                            [script, row["id"]], capture_output=True,
                            text=True, timeout=60)
                        tail = (r.stdout or r.stderr or "").strip() \
                            .splitlines()
                        msg = (f"✓ {row['label']}: connection "
                               f"script ran"
                               + (f" — {tail[-1]}" if tail else ""))
                    except Exception as e:
                        msg = (f"{row['label']}: the connection "
                               f"script failed ({e}); the switch "
                               f"stays on and the hub still reads it.")
                    GLib.idle_add(reach_status.set_text, msg)
                threading.Thread(target=run_script,
                                 daemon=True).start()
        state = state_cell.get("state")
        if state is not None:
            populates["dwell"](state)

    def pop_nodes(state):
        state_cell["state"] = state
        nodes_buf.set_text(nodes_text(state["crawl"],
                                      state["reports"]))
        while (child := reach_box.get_first_child()) is not None:
            reach_box.remove(child)
        enabled = load_reach_enabled()
        rows = reach_rows(state["crawl"])
        if not rows:
            lbl = Gtk.Label(label="The crawl found no organs or "
                                  "pipes to offer on this node.")
            lbl.set_xalign(0)
            lbl.set_margin_start(12)
            reach_box.append(lbl)
        for row in rows:
            rbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                           spacing=10)
            rbox.set_margin_start(12)
            rbox.set_margin_end(12)
            sw = Gtk.Switch()
            sw.set_active(bool(enabled.get(row["id"])))
            sw.set_sensitive(row["found"])
            sw.set_valign(Gtk.Align.START)
            sw.connect("notify::active", on_reach_toggle, row)
            texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                            spacing=2)
            lab = Gtk.Label(label=row["label"]
                            + ("" if row["found"]
                               else " — not found"))
            lab.set_xalign(0)
            det = Gtk.Label(label=f"{row['detail']} — suggests: "
                                  f"{row['suggests']}")
            det.set_xalign(0)
            det.set_wrap(True)
            texts.append(lab)
            texts.append(det)
            rbox.append(sw)
            rbox.append(texts)
            reach_box.append(rbox)

    populates["nodes"] = pop_nodes
    populates["dwell"] = lambda s: dwell_buf.set_text(
        dwell_text(s["social"], s["social_path"], s["crawl"],
                   reach_enabled=load_reach_enabled()))
    populates["watch"] = pop_watch

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
             ("Nodes", nodes_box), ("Dwell", dwell_sw),
             ("Roam Watch", watch_box), ("Help & Support", help_box)]
    for i, (title, widget) in enumerate(pages):
        if i == 0:
            notebook.insert_page(widget, Gtk.Label(label=title), 0)
        else:
            notebook.append_page(widget, Gtk.Label(label=title))
    notebook.set_current_page(0)

    greet_buf.set_text("Crawling this machine — measuring your hardware, "
                       "your models and your pipes. Your greeting is "
                       "measured, not guessed; this takes a few seconds.")

    def work():
        global _MODEL_POPUP_SHOWN
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
                    and load_options()["model_advice_popup"] \
                    and not _MODEL_POPUP_SHOWN \
                    and state["advice"]["state"] in ("keep", "upgrade", "none"):
                # Once per process, whoever rebuilds the window:
                # advice must never stack dialogs.
                _MODEL_POPUP_SHOWN = True
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
    # Custom shelves name by class: george-14, george-14:latest.
    m = re.search(r"-(\d+(?:\.\d+)?)\b", (name or "").lower())
    return float(m.group(1)) if m else None

def fetch_tags():
    """The door's shelf, or None if the door isn't answering."""
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags",
                                    timeout=2.5) as r:
            return json.load(r).get("models", [])
    except Exception:
        return None

def model_advice(crawl, tags):
    # The base function decides the fit: aptitude -> known model.
    # The popup, the installer and the greeting all read this one
    # pairing, so they can never give different advice.
    p = pairing_mod.pair(crawl["census"])
    fitted, fitted_p = p["model"], p["params_b"]
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
            "message": f"Your largest resident model is {resident}; the "
                       f"pairing for your hardware is {fitted} "
                       f"({p['mode']}). You can pull the "
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

        def done(d, result, _user_data=None):
            # PyGObject calls async callbacks as (source, result,
            # user_data) — three arguments. A two-argument version
            # died on every click and left this dialog stuck open
            # forever (reference laptop, 2026-11-17).
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

def service_links(watch):
    """Clickable service doors from a hub watch (Zak, 2026-11-17:
    'I should be able to do pretty much everything from that app,
    including click the links for Frigate'). Every suggestion whose
    linking options name an http door becomes a link — except
    credential pointers, which are information, not doors."""
    links, seen = [], set()
    if not watch:
        return links
    for s in watch.get("suggestions", []):
        for o in s.get("linking_options", []):
            target = (o.get("target") or "").strip()
            option = (o.get("option") or "").lower()
            if target.startswith("http") and "credential" not in option \
                    and target not in seen:
                seen.add(target)
                links.append({"service": s.get("service", "service"),
                              "url": target})
    return links

# ------------------------------------------- plain-language script options
# Zak (2026-11-17): the app needs an easy tool to adjust script
# options in plain language. These switches live on the landing page;
# each one names what it does in a sentence, persists to conduit.json,
# and is actually read by the behavior it describes.

SCRIPT_OPTIONS = [
    {"key": "model_advice_popup", "default": True,
     "label": "Model advice popup",
     "help": "When the app opens, it checks the models on this machine "
             "and pops up its advice — keep yours, or take the better "
             "fit. Off: the advice waits quietly on this page instead."},
    {"key": "service_links", "default": True,
     "label": "Clickable service doors",
     "help": "Roam Watch shows buttons that open your services "
             "(Frigate, the model door) in the browser. Off: names "
             "and addresses as plain text."},
    {"key": "watch_suggestions", "default": True,
     "label": "New-arrival suggestions",
     "help": "When the hourly watch spots a new device or service, "
             "its suggestion shows in Roam Watch. Off: the watch "
             "still runs; the page stays quiet about arrivals."},
]

def _load_conduit_json():
    try:
        with open(CONDUIT_JSON) as f:
            return json.load(f)
    except Exception:
        return {}

def _save_conduit_json(data):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(CONDUIT_JSON, "w") as f:
        json.dump(data, f, indent=1)

def load_options():
    saved = _load_conduit_json().get("options", {})
    return {o["key"]: bool(saved.get(o["key"], o["default"]))
            for o in SCRIPT_OPTIONS}


# ------------------------------------------------------------ reach map

def reach_rows(crawl):
    """The crawl reach map for THIS node (Zak, 2026-11-18):
    every organ and pipe the crawl found — or looked for — with
    the comparable use it suggests. The Nodes page renders these
    with switches; a switch is the user's confirmation, and the
    hub's dwell/roam set is exactly the switched-on rows."""
    c = crawl["census"]
    rows = []
    for cam in c.get("cameras", []):
        rows.append({"id": f"camera:{cam['device']}",
                     "kind": "camera", "found": True,
                     "label": f"Camera — {cam['name']}",
                     "detail": cam["device"],
                     "suggests": "a dwell eye and a roam source "
                                 "for the hub"})
    for a in c.get("audio", []):
        if a.get("capture"):
            rows.append({"id": f"mic:{a['card']}", "kind": "audio",
                         "found": True,
                         "label": f"Microphone — {a['name']}",
                         "detail": a["card"],
                         "suggests": "the parallel ear — attention "
                                     "and emergency never wait for "
                                     "the patrol"})
        if a.get("playback"):
            rows.append({"id": f"speaker:{a['card']}",
                         "kind": "audio", "found": True,
                         "label": f"Speaker — {a['name']}",
                         "detail": a["card"],
                         "suggests": "a voice for the hub to "
                                     "speak through"})
    for item in c.get("reach", []):
        rows.append({"id": f"reach:{item['id']}",
                     "kind": item["kind"],
                     "found": item["found"],
                     "label": item["id"],
                     "detail": item["detail"],
                     "suggests": item["suggests"]})
    return rows


def load_reach_enabled():
    return _load_conduit_json().get("reach_enabled", {})


def save_reach_enabled(item_id, on):
    data = _load_conduit_json()
    enabled = data.setdefault("reach_enabled", {})
    enabled[item_id] = bool(on)
    _save_conduit_json(data)
    return enabled


def connect_script_for(item_id):
    """The connection script for a reach item, when one exists:
    connect-<item>.sh under the user's ai-core scripts dir or
    the installed scripts dir. The switch runs it on enable;
    where none exists, the switch itself is the connection —
    the hub reads conduit.json — and the page says so."""
    safe = item_id.replace(":", "-").replace("/", "-")
    for d in (os.path.join(STATE_DIR, "scripts"),
              "/opt/ai-core/scripts"):
        p = os.path.join(d, f"connect-{safe}.sh")
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None

def save_option(key, value):
    data = _load_conduit_json()
    data.setdefault("options", {})[key] = bool(value)
    _save_conduit_json(data)
    return load_options()
