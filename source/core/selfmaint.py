"""Self-maintenance — the app builds and maintains itself, out of
the box, on the floor's own beats.

A GLOSS, in Zak's sense, is a detail that doesn't align with the
rounded plan. A GAP is a surface that promises what another surface
never built. On every wake and dwell beat (and at no other time —
the client wires this as the floor's companion), a CENSUS compares
the system's declared surfaces against each other:

  * client-advertised TOOL actions vs each service's implemented
    actions (handler tables read by AST from the ring sources)
  * README's advertised tokens and ports vs core.protocol
  * response keys the client's formatter expects vs what service
    sources ever return
  * config.json keys vs actual reads in app/core sources
  * ring folders on disk vs the wire registry
  * explainer coverage for the controls the client uses

Findings split by what may be done about them:

  SAFE FILLS — mechanical derivations from the contract itself,
  applied with a backup + a receipt, idempotent by construction:
  aligning the client/README advertisement to the services'
  reality through the declared alias table (reality wins), and
  generating a missing explainer entry. A second beat finds
  nothing to redo.

  PROPOSALS — everything beyond mechanical derivation: renaming
  a service action, changing a response shape, wiring a config
  read, the web legacy-health rename class. Filed once each
  (dedupe by finding id) as a .md under the proposals location;
  the owner's red pen decides. Never auto-applied.

Census results persist to the memory service under
selfmaint:<session>:census; fills announce themselves through
the client's check-in surface.

Expansion rides these same organs — there is no separate
expansion engine. A new script joins the build by two steps
only: SOURCE LABELED (a Label-* block, core.ring_service) and
ROUTED (its serve() route agreeing with core.protocol). The
census watches both: an unlabeled script is a safe-fill
finding (the label is mechanical — derived from the route);
an unrouted or port-drifted script is a proposal (joining the
registry is the owner's call). Self-maintenance itself works
through the app's own surfaces — receipts to the memory
service, backups and proposals to the state ring on disk.

The census also watches the two limits every approval lives
under: the DECLARED limit (what config/labels say) and the
ACTUAL limit (measured on this box). When they drift apart
unannounced, that is a gloss — the rule is that a declared
limit is only ever pushed past by providing power and data,
never by silently raising a number.
"""
import ast
import json
import re
import time
from pathlib import Path

from core.protocol import SERVICE_PORTS, mcp_call
from core.ring_service import (label_block, label_complete,
                               parse_label, serve_route)

MEMORY_PORT = SERVICE_PORTS["memory"]

# Advertised names that mean a service action that exists — the
# declared equivalence table. Aligning an advertisement through
# this table is mechanical; a mismatch with no alias is a
# proposal (renaming a service is someone's call).
ACTION_ALIASES = {
    "memory": {"store": "set", "recall": "get", "list_keys": "list"},
    "vision": {"list_cameras": "list", "capture": "grab"},
}

# Response keys the client's result formatter expects a service
# to return for an action (core/loop.py reads resp["result"] for
# coding eval). A service that never returns the key is a gloss.
EXPECTED_RESPONSE_KEYS = {"coding": {"eval": "result"}}

# Explainers the client's controls ask for by key.
REQUIRED_EXPLAINERS = ["theme", "floor", "model", "ring",
                       "calculator", "toy", "setup", "selfmaint"]

_TOKEN_RE = re.compile(r"TOOL:([a-z]+):([a-z_]+):")


def _finding(kind, subject, surfaces, evidence, fill_class,
             detail=""):
    fid = re.sub(r"[^a-z0-9]+", "-",
                 f"{kind}-{subject}".lower()).strip("-")
    return {"id": fid, "kind": kind, "subject": subject,
            "surfaces": surfaces, "evidence": evidence,
            "class": fill_class, "detail": detail}


def tree_layout(root):
    """Resolve the two layouts: the repo (source/ + README) and
    the installed tree (app/core/rings at the root)."""
    root = Path(root)
    src = root / "source" if (root / "source").is_dir() else root
    return {
        "root": root, "src": src,
        "client": src / "app" / "ai-client.py",
        "readme": root / "README.md",
        "config": src / "config.json",
        "rings": src / "rings",
        "core": src / "core",
        "app": src / "app",
    }


def _service_actions(rings_dir):
    """{service: set(actions)} from the ring sources' serve()
    handler tables (AST), plus the scaffold's health."""
    implemented = {}
    if not rings_dir.is_dir():
        return implemented
    for path in sorted(rings_dir.glob("*/*.py")):
        try:
            tree = ast.parse(path.read_text())
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Name)
                    and func.id == "serve"):
                continue
            if len(node.args) < 4:
                continue
            name_node, handlers = node.args[0], node.args[3]
            if not isinstance(name_node, ast.Constant) \
                    or not isinstance(handlers, ast.Dict):
                continue
            actions = {k.value for k in handlers.keys
                       if isinstance(k, ast.Constant)}
            actions.add("health")  # the scaffold's citizen
            implemented[name_node.value] = actions
    return implemented


def _advertised(text):
    return set(_TOKEN_RE.findall(text))


def census(root, profile=None):
    """Compare the declared surfaces. Returns finding dicts.
    Read-only — a census never changes anything. `profile`
    (optional core.setup hardware profile) enables the
    declared-vs-actual limits check."""
    lay = tree_layout(root)
    findings = []
    implemented = _service_actions(lay["rings"])

    # 1. Advertised vs implemented, per advertising surface.
    surfaces = []
    if lay["client"].exists():
        surfaces.append(("client", lay["client"]))
    if lay["readme"].exists():
        surfaces.append(("README", lay["readme"]))
    for label, path in surfaces:
        for svc, action in sorted(_advertised(
                path.read_text(errors="ignore"))):
            have = implemented.get(svc)
            if have is None:
                findings.append(_finding(
                    "gap", f"{svc}-service-missing",
                    [label, svc],
                    f"{label} advertises TOOL:{svc}:… but no "
                    f"service named {svc} exists in the rings",
                    "proposal"))
            elif action not in have:
                alias = ACTION_ALIASES.get(svc, {}).get(action)
                if alias and alias in have:
                    findings.append(_finding(
                        "gap", f"{label}-{svc}-{action}",
                        [label, svc],
                        f"{label} advertises TOOL:{svc}:{action}; "
                        f"the {svc} service implements "
                        f"{sorted(have)} — the alias table maps "
                        f"{action} → {alias}",
                        "safe",
                        detail=f"rewrite {label} to advertise "
                               f"TOOL:{svc}:{alias}"))
                else:
                    findings.append(_finding(
                        "gap", f"{label}-{svc}-{action}",
                        [label, svc],
                        f"{label} advertises TOOL:{svc}:{action}; "
                        f"the {svc} service implements "
                        f"{sorted(have)} and no alias covers it",
                        "proposal",
                        detail="renaming a service action is the "
                               "owner's call"))

    # 2. Response keys the formatter expects vs service sources.
    for svc, by_action in EXPECTED_RESPONSE_KEYS.items():
        files = list(lay["rings"].glob(f"*/mcp-{svc}.py"))
        if not files:
            continue
        text = files[0].read_text(errors="ignore")
        for action, key in by_action.items():
            if f'"{key}"' not in text and f"'{key}'" not in text:
                findings.append(_finding(
                    "gloss", f"{svc}-{action}-response-{key}",
                    [svc, "client-formatter"],
                    f"the client's formatter expects response "
                    f"key {key!r} for {svc} {action}; the service "
                    f"source never returns it",
                    "proposal",
                    detail="changing a response shape is behavior; "
                           "the owner decides which side moves"))

    # 3. Config keys vs actual reads.
    if lay["config"].exists():
        try:
            cfg = json.loads(lay["config"].read_text())
        except ValueError:
            cfg = None
        if isinstance(cfg, dict):
            # The client is the config's consumer; only its reads
            # count (a .get("model") on some other dict elsewhere
            # in the tree is not the config being honored).
            corpus = ""
            if lay["client"].exists():
                corpus = lay["client"].read_text(errors="ignore")
            for key in cfg:
                pat = re.compile(r"\.get\(\s*[\"']" + re.escape(key)
                                 + r"[\"']|\[\s*[\"']"
                                 + re.escape(key) + r"[\"']\s*\]")
                if not pat.search(corpus):
                    findings.append(_finding(
                        "gloss", f"config-{key}-unread",
                        ["config", "client"],
                        f"config.json offers {key!r}; no app/core "
                        f"source ever reads it — the value is "
                        f"decoration until wired",
                        "proposal",
                        detail="the wiring is a pure read, but it "
                               "changes runtime behavior — red pen"))

    # 4. Registry vs disk vs config ports.
    on_disk = set(implemented)
    for svc in sorted(set(SERVICE_PORTS) - on_disk):
        findings.append(_finding(
            "gap", f"{svc}-not-on-disk", ["registry", svc],
            f"core.protocol routes {svc} on "
            f"{SERVICE_PORTS[svc]} but no ring source implements "
            f"it", "proposal"))
    if lay["config"].exists():
        try:
            cfg = json.loads(lay["config"].read_text())
            ports = cfg.get("mcp_ports") or {}
        except ValueError:
            ports = {}
        for svc, port in SERVICE_PORTS.items():
            if svc in ports and ports[svc] != port:
                findings.append(_finding(
                    "gloss", f"{svc}-port-drift",
                    ["config", "protocol"],
                    f"config.json puts {svc} on {ports[svc]}; "
                    f"core.protocol routes {port}", "proposal"))

    # 5. Docs ports (README) vs the wire contract.
    if lay["readme"].exists():
        text = lay["readme"].read_text(errors="ignore")
        for svc, port in SERVICE_PORTS.items():
            if str(port) not in text:
                findings.append(_finding(
                    "gloss", f"readme-{svc}-port", ["README", svc],
                    f"README never mentions {svc}'s port {port}",
                    "proposal"))

    # 6. Explainer coverage.
    try:
        from core import learn
        have = set(learn.EXPLAINERS) | set(learn.GENERATED)
    except Exception:
        have = set()
    for key in REQUIRED_EXPLAINERS:
        if key not in have:
            findings.append(_finding(
                "gap", f"explainer-{key}", ["explainers", key],
                f"the client asks for explainer {key!r}; the "
                f"registry has no entry",
                "safe",
                detail="generate an entry from the system's own "
                       "records, labeled generated"))

    # 7. The web legacy-health class.
    web_files = list(lay["rings"].glob("*/mcp-web.py"))
    if web_files:
        try:
            tree = ast.parse(web_files[0].read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) \
                        and isinstance(node.func, ast.Name) \
                        and node.func.id == "serve" \
                        and len(node.args) >= 4 \
                        and isinstance(node.args[3], ast.Dict):
                    keys = {k.value for k in node.args[3].keys
                            if isinstance(k, ast.Constant)}
                    if "health" in keys:
                        findings.append(_finding(
                            "gloss", "web-legacy-health",
                            ["web", "ring-convention"],
                            "web's health predates the ring "
                            "convention (it probes internet "
                            "reachability); every other service's "
                            "health is the transductive self-"
                            "report", "proposal",
                            detail="renaming web's health is the "
                                   "known legacy class — owner's "
                                   "call, documented either way"))
        except SyntaxError:
            pass

    # 8. Script plugs: source labeled + routed.
    if lay["rings"].is_dir():
        for path in sorted(lay["rings"].glob("*/*.py")):
            text = path.read_text(errors="ignore")
            route = serve_route(text)
            if route is None:
                continue  # not a service script
            name = route["name"]
            if not label_complete(parse_label(text)):
                findings.append(_finding(
                    "gap", f"label-{name}", ["labels", name],
                    f"{path.name} routes as {name} but carries "
                    f"no complete Label-* block — a script joins "
                    f"the build labeled, or it does not join",
                    "safe",
                    detail="backfill a label block derived "
                           "from the serve() route (mechanical)"))
            routed = SERVICE_PORTS.get(name)
            if routed is None:
                findings.append(_finding(
                    "gloss", f"route-{name}-unregistered",
                    ["routes", name],
                    f"{path.name} serves as {name} on "
                    f"{route['port']} but core.protocol has no "
                    f"route for it — unrouted scripts are "
                    f"findings, never silently enabled",
                    "proposal",
                    detail="joining the registry is the "
                           "owner's call"))
            elif routed != route["port"]:
                findings.append(_finding(
                    "gloss", f"route-{name}-port-drift",
                    ["routes", "protocol"],
                    f"{path.name} serves {name} on "
                    f"{route['port']}; core.protocol routes "
                    f"{routed}", "proposal"))

    # 9. Declared vs actual limits (needs a measured profile).
    if profile:
        cfg = None
        if lay["config"].exists():
            try:
                cfg = json.loads(lay["config"].read_text())
            except ValueError:
                cfg = None
        declared = (cfg or {}).get("model") or ""
        m = re.search(r"(\d+(?:\.\d+)?)b", declared)
        if m:
            params = float(m.group(1))
            usable = profile.get("vram_gb") or round(
                0.6 * (profile.get("ram_gb") or 0), 1)
            if usable and usable < params:
                findings.append(_finding(
                    "gloss", "limits-declared-vs-actual",
                    ["config", "hardware"],
                    f"config declares model {declared!r} "
                    f"(~{params:g}B) but this box measures "
                    f"~{usable:g} GB usable for a local model — "
                    f"declared and actual limits have drifted "
                    f"apart, unannounced",
                    "proposal",
                    detail="to push past a declared limit you "
                           "provide power and data — a bigger "
                           "local model, more headroom, an API "
                           "tier, more storage; the app never "
                           "just raises a number"))
    return findings


# --- Safe fills ------------------------------------------------------------

def _backup(state_dir, path, ts):
    backups = Path(state_dir) / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    dest = backups / f"{path.name}.bak-{ts}"
    dest.write_bytes(path.read_bytes())
    return str(dest)


def apply_safe_fills(root, state_dir, findings, ts=None):
    """Apply the mechanical fills. Each returns a receipt; each
    is idempotent — run it twice, the second run receipts
    nothing. Proposal-class findings are never touched here."""
    ts = ts or time.strftime("%Y%m%d-%H%M%S")
    state_dir = Path(state_dir)
    lay = tree_layout(root)
    receipts = []
    for f in findings:
        if f["class"] != "safe":
            continue
        if f["id"].startswith(("gap-client-", "gap-readme-")):
            label = "client" if f["id"].startswith("gap-client-") \
                else "README"
            path = lay["client"] if label == "client" \
                else lay["readme"]
            # Parse from the subject, not the id: the id is
            # slugged (underscores become hyphens), the subject
            # keeps the true action name.
            rest = f["subject"].split("-", 1)[1]
            svc, action = rest.split("-", 1)
            alias = ACTION_ALIASES.get(svc, {}).get(action)
            if not alias or not path.exists():
                continue
            text = path.read_text(errors="ignore")
            old = f"TOOL:{svc}:{action}:"
            if old not in text:
                continue  # already aligned — nothing to redo
            backup = _backup(state_dir, path, ts)
            path.write_text(text.replace(old,
                                         f"TOOL:{svc}:{alias}:"))
            receipts.append({
                "finding": f["id"], "action": "align-advertisement",
                "file": str(path), "backup": backup,
                "change": f"{old} → TOOL:{svc}:{alias}:",
                "ts": ts})
        elif f["id"].startswith("gap-label-"):
            name = f["subject"].removeprefix("label-")
            path = route = None
            if lay["rings"].is_dir():
                for cand in sorted(lay["rings"].glob("*/*.py")):
                    r = serve_route(cand.read_text(
                        errors="ignore"))
                    if r and r["name"] == name:
                        path, route = cand, r
                        break
            if path is None:
                continue
            text = path.read_text(errors="ignore")
            if label_complete(parse_label(text)):
                continue  # labeled since the census — no redo
            backup = _backup(state_dir, path, ts)
            block = label_block(
                name, "ai-core-workspace build", "1",
                f"{route['ring']} ring service on port "
                f"{route['port']} (label backfilled by "
                f"self-maintenance from the serve() route)")
            path.write_text(block + "\n" + text)
            receipts.append({
                "finding": f["id"], "action": "backfill-label",
                "file": str(path), "backup": backup,
                "change": f"label block added for {name}",
                "ts": ts})
        elif f["id"].startswith("gap-explainer-"):
            key = f["subject"].removeprefix("explainer-")
            gen_path = state_dir / "generated_explainers.json"
            gen = {}
            if gen_path.exists():
                try:
                    gen = json.loads(gen_path.read_text())
                except ValueError:
                    gen = {}
            if key in gen:
                continue
            gen[key] = generate_explainer(key)
            state_dir.mkdir(parents=True, exist_ok=True)
            gen_path.write_text(json.dumps(gen, indent=2))
            receipts.append({
                "finding": f["id"], "action": "generate-explainer",
                "file": str(gen_path), "key": key, "ts": ts})
    return receipts


def generate_explainer(key, health=None):
    """An explainer entry generated from the system's own records
    (a service's health self-report when one is at hand), labeled
    as generated — a placeholder with its provenance on its face,
    inviting the red pen."""
    if health:
        plain = (f"{health.get('service', key)}: a "
                 f"{health.get('ring', '?')}-ring service on port "
                 f"{health.get('port', '?')}, answering for itself "
                 f"in-band. (Explainer generated by self-"
                 f"maintenance from its health report.)")
    else:
        plain = (f"Explainer for {key}, generated by self-"
                 f"maintenance because the registry had none — "
                 f"plain placeholder, provenance stated, red pen "
                 f"invited.")
    return {"plain": plain,
            "story": "Generated on a dwell beat when the census "
                     "found this control explaining itself to "
                     "nobody.",
            "tech": "Source: core/selfmaint.py generate_explainer"
                    "(); hand-written entries in core/learn.py "
                    "always win over generated ones."}


# --- Proposals ---------------------------------------------------------------

def file_proposals(state_dir, findings, ts=None):
    """File each proposal-class finding once (dedupe by id) as a
    .md under proposals/. Returns the newly filed paths."""
    ts = ts or time.strftime("%Y-%m-%d %H:%M")
    pdir = Path(state_dir) / "proposals"
    pdir.mkdir(parents=True, exist_ok=True)
    filed = []
    for f in findings:
        if f["class"] != "proposal":
            continue
        path = pdir / f"{f['id']}.md"
        if path.exists():
            continue
        path.write_text(
            f"# Proposal: {f['subject']}\n\n"
            f"- Kind: {f['kind']} (a detail that doesn't align "
            f"with the rounded plan)\n"
            f"- Surfaces: {', '.join(f['surfaces'])}\n"
            f"- Filed: {ts} by the self-maintenance census\n"
            f"- Status: WAITING for the owner's red pen — never "
            f"auto-applied.\n\n"
            f"## Evidence\n\n{f['evidence']}\n\n"
            f"## Note\n\n{f['detail']}\n")
        filed.append(str(path))
    return filed


def waiting_proposals(state_dir):
    pdir = Path(state_dir) / "proposals"
    if not pdir.is_dir():
        return []
    return sorted(p.name for p in pdir.glob("*.md"))


# --- The loop ------------------------------------------------------------------

class SelfMaintainer:
    """Census + fills + proposals on the floor's beats, recorded
    to the memory service. Never raises into the floor."""

    def __init__(self, root, state_dir=None, session="app",
                 call=None, port=MEMORY_PORT):
        self.root = root
        self.state_dir = Path(state_dir) if state_dir \
            else Path(root) / "selfmaint"
        self.session = session
        self._call = call or mcp_call
        self.port = port
        self.last_result = None
        self.unannounced_fills = 0

    def run_beat(self, beat, profile=None):
        try:
            findings = census(self.root, profile=profile)
            receipts = apply_safe_fills(self.root, self.state_dir,
                                        findings)
            filed = file_proposals(self.state_dir, findings)
            self.unannounced_fills += len(receipts)
            self.last_result = {
                "beat": beat,
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "findings": findings,
                "fills": receipts,
                "proposals_new": filed,
                "proposals_waiting": waiting_proposals(
                    self.state_dir),
            }
            self._call(self.port, {
                "action": "set",
                "key": f"selfmaint:{self.session}:census",
                "value": json.dumps(self.last_result)}, timeout=2)
            return self.last_result
        except Exception:
            return None

    def take_announcement(self):
        """How many fills landed since the client last announced
        them (the check-in surface reads and resets this)."""
        n = self.unannounced_fills
        self.unannounced_fills = 0
        return n
