#!/usr/bin/env bash
# ======================================================================
# AI Core Framework - Intelligent Hardware-Adapting Advanced Installer
# Includes: uninstall mode, post-install validation, backup guidance
# ======================================================================
set -euo pipefail
# Build banner: a stale checkout announces itself on line one. If
# this does not say "conduit build", the tree is the old app —
# stop and re-clone. (Learned 2026-11-17: a failed clone silently
# left a stale tree in place, and it installed v1 again.)
echo "🧭 AI Core installer — conduit build (pairing + merge)."

TARGET_DIR="/opt/ai-core"
SYSTEMD_DIR="/etc/systemd/system"
DESKTOP_DIR="/usr/share/applications"
MCP_NODES=("files" "web" "vision" "shell" "sound" "voice" "coding" "memory")
# Geometrically nested layout: each service lives in its ring under
# source/rings/ (see docs/GEOMETRIC_NESTING.md). Names/ports unchanged.
declare -A MCP_RING=( [files]=actuation [shell]=actuation [memory]=state [coding]=state [web]=atmosphere [vision]=atmosphere [sound]=atmosphere [voice]=atmosphere )

# Who the install is FOR — computed before every mode, uninstall
# included: the uninstall block uses $REAL_HOME, and under set -u
# the late definition crashed the uninstall itself on line 32
# before it removed anything (reference laptop, 2026-11-17).
REAL_USER="${SUDO_USER:-$(logname 2>/dev/null || echo "$USER")}"
REAL_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)

# --- UNINSTALL ---
if [[ "${1:-}" == "uninstall" ]]; then
    echo "🗑️ Uninstalling AI Core..."
    for name in "${MCP_NODES[@]}"; do
        systemctl stop "ai-mcp-$name.service" 2>/dev/null || true
        systemctl disable "ai-mcp-$name.service" 2>/dev/null || true
        rm -f "$SYSTEMD_DIR/ai-mcp-$name.service"
    done
    rm -f /usr/local/bin/ai-client
    rm -f /usr/local/bin/ai-core-report
    rm -f /usr/local/bin/ai-core-update
    systemctl stop ai-core-update.timer 2>/dev/null || true
    systemctl disable ai-core-update.timer 2>/dev/null || true
    rm -f "$SYSTEMD_DIR/ai-core-update.service"
    rm -f "$SYSTEMD_DIR/ai-core-update.timer"
    rm -f "$DESKTOP_DIR/ai-core.desktop"
    rm -f "$REAL_HOME/.config/autostart/ai-core.desktop" 2>/dev/null || true
    rm -rf "$TARGET_DIR"
    systemctl daemon-reload
    echo "✅ AI Core uninstalled. /opt/ai-core removed. MCP services stopped."
    echo "💡 Left in place, by design: Ollama itself and its models, the"
    echo "   ai-core.conf drop-in (if the app wrote one), and your choices"
    echo "   in ~/.config/ai-core. Remove those by hand for a clean slate."
    exit 0
fi

# --- PRIVILEGE CHECK ---
# (REAL_USER/REAL_HOME are defined above the uninstall block.)
if [[ $EUID -ne 0 ]]; then
   echo "⚠️ Administrative privileges required. Re-routing via sudo..."
   exec sudo bash "$0" "$@"
fi

# Work from the installer's own directory: every step below uses
# repo-relative paths, and a launch from elsewhere must not die
# mid-deploy on a missing file.
cd "$(dirname "$0")"
SRC_DIR="$(pwd)"
SRC_COMMIT="$(git -C "$SRC_DIR" rev-parse HEAD 2>/dev/null || echo unknown)"

# --- BACKUP EXISTING INSTALL ---
if [[ -d "$TARGET_DIR" ]]; then
    BACKUP="$TARGET_DIR.backup.$(date +%Y%m%d_%H%M%S)"
    echo "📦 Backing up existing install to $BACKUP"
    cp -a "$TARGET_DIR" "$BACKUP"
fi

echo "📦 Step 1: Resolving baseline Linux runtime packages..."
if command -v apt-get &>/dev/null; then
    apt-get update && apt-get install -y python3 python3-gi python3-gi-cairo libgtk-4-dev gir1.2-gtk-4.0 libadwaita-1-dev gir1.2-adw-1 libgirepository1.0-dev libcairo2-dev curl lshw pciutils ffmpeg
elif command -v dnf &>/dev/null; then
    dnf install -y python3 python3-gobject cairo-gobject-devel libgirepository-devel gtk4 libadwaita curl lshw pciutils ffmpeg
elif command -v pacman &>/dev/null; then
    pacman -Sy --needed --noconfirm python python-gobject cairo gtk4 libadwaita curl lshw pciutils ffmpeg
fi

echo "🧠 Step 2: Measuring hardware aptitude — the base function pairs it with a known model..."
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
TOTAL_RAM_GB=$(( TOTAL_RAM_KB / 1024 / 1024 ))
echo "📊 Detected RAM: ${TOTAL_RAM_GB}GB"

# Aptitude -> known model -> layer plan (core/pairing.py). The same
# pairing drives the first-launch popup, so installer and app agree.
OPTIMAL_MODEL=""
PAIR_MODE=""; PAIR_GPU_LAYERS=""; PAIR_TOTAL_LAYERS=""
PAIR_DIR=$(mktemp -d)
if python3 source/core/census.py --out "$PAIR_DIR" >/dev/null 2>&1; then
    PAIR_LINE=$(python3 - "$PAIR_DIR" <<'PAIR_EOF' 2>/dev/null || true
import json, os, sys
sys.path.insert(0, "source")
from core import pairing
c = json.load(open(os.path.join(sys.argv[1], "expectations.json")))
p = pairing.pair(c)
gl = "" if p["gpu_layers"] is None else str(p["gpu_layers"])
tl = "" if p["total_layers"] is None else str(p["total_layers"])
print(f"{p['model']}|{p['mode']}|{gl}|{tl}|{p['size_gb']}")
PAIR_EOF
)
    if [ -n "$PAIR_LINE" ]; then
        IFS='|' read -r OPTIMAL_MODEL PAIR_MODE PAIR_GPU_LAYERS PAIR_TOTAL_LAYERS PAIR_SIZE_GB <<< "$PAIR_LINE"
    fi
fi
if [ -n "$OPTIMAL_MODEL" ]; then
    echo "🎙️ Paired: $OPTIMAL_MODEL — $PAIR_MODE"
    [ -n "$PAIR_GPU_LAYERS" ] && echo "   Layers: $PAIR_GPU_LAYERS of $PAIR_TOTAL_LAYERS on the GPU (set when the talking model is created)"
else
    # The pairing could not run in this environment: fall back to
    # the coarse RAM rule rather than dying on the base function.
    if [ "$TOTAL_RAM_GB" -ge 16 ]; then OPTIMAL_MODEL="qwen3.5:9b"; else OPTIMAL_MODEL="qwen3:8b"; fi
    echo "⚠️ Pairing unavailable — coarse fallback selected: $OPTIMAL_MODEL"
fi

echo "🎮 Step 3: GPU detection..."
GPU_VENDOR="CPU"
if lspci | grep -qi "nvidia"; then GPU_VENDOR="NVIDIA"; echo "🚀 NVIDIA GPU"
elif lspci | grep -qi "amd\|ati"; then GPU_VENDOR="AMD"; echo "🔮 AMD GPU"
fi

echo "🦙 Step 4: Ollama — merging with what's here, never overwriting it..."
DROPIN_DIR="/etc/systemd/system/ollama.service.d"
APP_ENV_CHANGED=false
if ! command -v ollama &>/dev/null; then
    echo "📥 Installing Ollama..."
    # Run the upstream installer as root — this script already holds
    # root (see the privilege check). Dropping to the user first made
    # the upstream script's own sudo calls fail with no TTY to read a
    # password, leaving no ollama at all (reference laptop, 2026-11-17).
    curl -fsSL https://ollama.com/install.sh | sh || true
fi

# An owner-tuned Ollama (any drop-in of theirs) is merged with, not
# overwritten: their environment, their models path, their seats.
# The app writes only its OWN drop-in file, and only when the owner
# has none — and it never restarts a running door over nothing.
OWNER_DROPINS=$(ls "$DROPIN_DIR" 2>/dev/null | grep -v '^ai-core\.conf$' || true)
if [ -n "$OWNER_DROPINS" ]; then
    echo "🔒 Merge mode: found your Ollama configuration ($(echo $OWNER_DROPINS | tr '\n' ' '))."
    echo "   Kept exactly as-is — nothing written, nothing restarted."
    echo "   The app will use your model door as found."
elif [ ! -f "$DROPIN_DIR/ai-core.conf" ]; then
    mkdir -p "$DROPIN_DIR"
    # The service shape is paired to the aptitude too: on a small
    # machine a resident-forever model with parallel seats is how a
    # laptop locks up (reference laptop, 2026-11-17). Small shape:
    # one seat, models unload after 5 idle minutes.
    if [ "$TOTAL_RAM_GB" -lt 12 ]; then
        NUM_PARALLEL=1; KEEP_ALIVE="5m"
        echo "🧩 Small-machine service shape: one seat at a time, models unload when idle."
    else
        NUM_PARALLEL=2; KEEP_ALIVE="-1"
    fi
    {
        echo "[Service]"
        echo "Environment=\"OLLAMA_NUM_PARALLEL=$NUM_PARALLEL\""
        echo "Environment=\"OLLAMA_KEEP_ALIVE=$KEEP_ALIVE\""
        if [ "$GPU_VENDOR" = "NVIDIA" ]; then
            echo 'Environment="CUDA_VISIBLE_DEVICES=0"'
        elif [ "$GPU_VENDOR" = "AMD" ]; then
            echo 'Environment="HSA_OVERRIDE_GFX_VERSION=10.3.0"'
        fi
    } > "$DROPIN_DIR/ai-core.conf"
    APP_ENV_CHANGED=true
    echo "🧩 Wrote the app's own drop-in (ai-core.conf) — your files untouched."
fi

systemctl daemon-reload
if ! systemctl is-active --quiet ollama.service; then
    systemctl enable ollama.service --now || true
elif $APP_ENV_CHANGED; then
    echo "🔄 Restarting Ollama once so the app's drop-in takes effect..."
    systemctl restart ollama.service || true
fi

# The door gets real time to come up: a single check races the
# service start and can call a healthy door dead — and the old flow
# then mistook a dead door for an empty shelf and sailed on to a
# success banner. Both halves were named on 2026-11-17; the wait
# below and the INCOMPLETE verdict are the fix.
wait_for_door() {
    for _ in $(seq 1 15); do
        curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && return 0
        sleep 2
    done
    return 1
}
DOOR_OK=false
if wait_for_door; then DOOR_OK=true; fi

# The base function completes here (Zak's definition): size a
# model for the hardware, download it, install it, seat it, set
# its balanced smarts. Existing models are never removed and
# never pulled over — but a shelf holding only OTHER sizes is
# not a completed pairing. On 2026-11-17 a laptop kept two 8Bs,
# the paired 3B was never pulled because the shelf was non-empty,
# and the app defaulted to a model the kernel OOM-killed.
# In merge mode (an owner's own Ollama config) all of this is
# hands-off: list, pick the resident default, touch nothing.
SED_MODEL="$OPTIMAL_MODEL"
SEAT_OK=false
SEAT_CHECKED=false
if $DOOR_OK; then
    echo "✅ Ollama API responding"
    TAGS_JSON=$(curl -s http://127.0.0.1:11434/api/tags)
    EXISTING_MODELS=$(echo "$TAGS_JSON" | python3 -c "import json,sys; print(' '.join(m['name'] for m in json.load(sys.stdin).get('models', [])))" 2>/dev/null || true)
    if [ -n "$EXISTING_MODELS" ]; then
        echo "📚 Models already on this machine: $EXISTING_MODELS"
    fi
    if [ -n "$OWNER_DROPINS" ]; then
        PICK=$(echo "$TAGS_JSON" | python3 -c "
import json, re, sys
def p(n):
    m = re.search(r'(\d+(?:\.\d+)?)\s*b\b', n.lower())
    if m: return float(m.group(1))
    m = re.search(r'-(\d+(?:\.\d+)?)\b', n.lower())
    return float(m.group(1)) if m else 0
names = [m['name'] for m in json.load(sys.stdin).get('models', [])]
print(sorted(names, key=p, reverse=True)[0] if names else '')" 2>/dev/null || true)
        [ -n "$PICK" ] && SED_MODEL="$PICK"
        echo "   Merge mode: your shelf is yours — nothing pulled, created,"
        echo "   or seated. The app defaults to $SED_MODEL and advises in-app."
    else
        PAIRED_PRESENT=false
        case " $EXISTING_MODELS " in
            *" $OPTIMAL_MODEL "*) PAIRED_PRESENT=true ;;
        esac
        if ! $PAIRED_PRESENT; then
            echo "📥 The paired model for this hardware is $OPTIMAL_MODEL — pulling it now."
            [ -n "${PAIR_SIZE_GB:-}" ] && echo "   (~${PAIR_SIZE_GB} GB download — this is the long step; everything after it is quick.)"
            if su - "$REAL_USER" -c "ollama pull $OPTIMAL_MODEL 2>/dev/null"; then
                PAIRED_PRESENT=true
            else
                echo "⚠️ Model pull deferred (run: ollama pull $OPTIMAL_MODEL)"
            fi
        fi
        if $PAIRED_PRESENT; then
            # The talking model is built FROM the paired model,
            # with this hardware's layer plan and the balanced
            # settings (temperature 0.6 — the house balanced point
            # for smarts and speed). Rebuilt whenever its base is
            # not the current pairing; the base stays untouched.
            TALKING_PARENT=$(curl -s -X POST http://127.0.0.1:11434/api/show -d '{"name": "ai-core-talking"}' 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin).get('details', {}).get('parent_model', ''))" 2>/dev/null || true)
            if [ "$TALKING_PARENT" != "$OPTIMAL_MODEL" ]; then
                MODFILE=$(mktemp /tmp/ai-core-modelfile.XXXXXX)
                chmod 644 "$MODFILE"
                printf "FROM %s\nPARAMETER num_gpu %s\nPARAMETER temperature 0.6\n" "$OPTIMAL_MODEL" "${PAIR_GPU_LAYERS:-0}" > "$MODFILE"
                if su - "$REAL_USER" -c "ollama create ai-core-talking -f $MODFILE" 2>/dev/null; then
                    echo "🎙️ Talking model set: ai-core-talking (from $OPTIMAL_MODEL, ${PAIR_GPU_LAYERS:-0} of ${PAIR_TOTAL_LAYERS:-?} layers on the GPU, balanced temperature 0.6)"
                    SED_MODEL="ai-core-talking"
                else
                    echo "⚠️ Talking-model build deferred — the app will use $OPTIMAL_MODEL directly."
                fi
                rm -f "$MODFILE"
            else
                echo "🎙️ Talking model already built from the paired model ($OPTIMAL_MODEL)."
                SED_MODEL="ai-core-talking"
            fi
            # Seat it, and prove the seat in ollama ps — an
            # install that never seated its voice has not
            # finished the base function.
            SEAT_CHECKED=true
            if curl -s -X POST http://127.0.0.1:11434/api/generate -d "{\"model\": \"$SED_MODEL\", \"prompt\": \"\", \"keep_alive\": \"30m\", \"stream\": false}" >/dev/null 2>&1 \
               && curl -s http://127.0.0.1:11434/api/ps 2>/dev/null | grep -q "\"name\": \"$SED_MODEL\""; then
                SEAT_OK=true
                echo "🪑 Seated and proven in ollama ps: $SED_MODEL"
            else
                echo "⚠️ $SED_MODEL did not seat — validation will count it."
            fi
        fi
    fi
else
    echo "🛑 The model door (Ollama) is NOT answering after a 30-second wait."
    echo "   The base function cannot complete against a silent door: no"
    echo "   model can be pulled, layered, or verified. The app still"
    echo "   deploys (it works as an observer), but this install is"
    echo "   INCOMPLETE — the final banner will say exactly that."
    echo "   Check: journalctl -u ollama -n 20"
fi

echo "🛰️  Step 4.5: Crawling this machine — the conduit's first job."
echo "   What it finds decides your tiers, your model fit, and the promises"
echo "   the landing page will make. Learned knowledge, as it arrives:"
CRAWL_DIR=$(mktemp -d)
if python3 source/core/census.py --out "$CRAWL_DIR" >/dev/null 2>&1 \
   && python3 source/core/pipes.py --out "$CRAWL_DIR" >/dev/null 2>&1; then
    mkdir -p "$TARGET_DIR/crawl" 2>/dev/null || true
    cp "$CRAWL_DIR/expectations.json" "$CRAWL_DIR/pipes.json" "$TARGET_DIR/crawl/" 2>/dev/null || true
    python3 - "$CRAWL_DIR" "$OPTIMAL_MODEL" <<'CRAWL_EOF' || echo "   (narration skipped — the crawl itself is saved under $TARGET_DIR/crawl)"
import json, os, sys
d, optimal = sys.argv[1], sys.argv[2]
c = json.load(open(os.path.join(d, "expectations.json")))
p = json.load(open(os.path.join(d, "pipes.json")))
exp = c["expectations"]; tiers = {t["tier"]: t for t in exp["tiers"]}
print(f"   🖥️  {c['host']}: {c['cpu']['effective_threads']} effective threads, "
      f"{round(c['ram']['effective_mb']/1024, 1)} GB usable RAM, "
      f"{('GPU: ' + ', '.join(g.get('name') or (g.get('vendor', 'GPU') + ' GPU') for g in c['gpus'])) if c['gpus'] else 'no GPU'}")
print(f"   🎚️  Budget: {exp['budget']['max_parallel_model_tasks']} model task(s) at once. "
      "Script tasks are never seat-bound — the floor is always up.")
conv = tiers.get("conversation", {})
print(f"   💬 Conversation: {conv.get('status', 'unknown')} — "
      f"{conv.get('expectation') or conv.get('announcement', '')}")
if not c["gpus"]:
    print("   💡 No GPU found: models take CPU seats here. Speeds on the landing "
          "page are written for CPU — honest numbers, not brochure numbers.")
if "resident" not in conv.get("status", ""):
    print(f"   💡 Your conversation model isn't resident yet. The fit for this "
          f"machine is {optimal} — pull it with: ollama pull {optimal}")
if tiers.get("knowledge (web)", {}).get("status", "").startswith("available"):
    print("   💡 Web knowledge is reachable: even a small local model answers "
          "above its weight here. Low tier is a tier, not a handicap.")
print(f"   🔌 Pipes recognized: {len(p['pipes_found'])} "
      f"({', '.join(x['id'] for x in p['pipes_found']) or 'none yet'}) — "
      "each gets a feed and a lane in the hub.")
for o in p["script_tier_offers"]:
    print(f"   ✨ Script tier unlocked: {o['offer']}")
CRAWL_EOF
else
    echo "   ⚠️ The crawl could not run in this environment — the app crawls"
    echo "      again on first launch and will show what it finds there."
fi

echo "📂 Step 5: Deploying files..."
mkdir -p "$TARGET_DIR/app" "$TARGET_DIR/core" "$TARGET_DIR/rings/state" "$TARGET_DIR/rings/actuation" "$TARGET_DIR/rings/atmosphere"
cp -r source/core/* "$TARGET_DIR/core/"
cp -r source/rings/state/* "$TARGET_DIR/rings/state/"
cp -r source/rings/actuation/* "$TARGET_DIR/rings/actuation/"
cp -r source/rings/atmosphere/* "$TARGET_DIR/rings/atmosphere/"
cp -r source/app/* "$TARGET_DIR/app/"
cp source/config.json "$TARGET_DIR/config.json" 2>/dev/null || true
chmod +x "$TARGET_DIR/app/ai-client.py"

sed -i "s/self.model = \"qwen3.5:9b\"/self.model = \"$SED_MODEL\"/g" "$TARGET_DIR/app/ai-client.py"
sed -i "s/return \[\".*:9b\"\]/return [\"$SED_MODEL\"]/g" "$TARGET_DIR/app/ai-client.py"

echo "⚙️ Step 6: MCP services..."
for name in "${MCP_NODES[@]}"; do
    cat << SVC_EOF > "$SYSTEMD_DIR/ai-mcp-$name.service"
[Unit]
Description=AI Core MCP ($name)
After=network.target

[Service]
ExecStart=/usr/bin/python3 $TARGET_DIR/rings/${MCP_RING[$name]}/mcp-$name.py
Restart=always
RestartSec=2
User=$REAL_USER

[Install]
WantedBy=multi-user.target
SVC_EOF
    systemctl enable "ai-mcp-$name.service" --now 2>/dev/null || true
    systemctl restart "ai-mcp-$name.service" 2>/dev/null || true
done

echo "🔗 Step 7: Desktop integration..."
cat << 'BIN_EOF' > /usr/local/bin/ai-client
#!/usr/bin/env bash
exec /usr/bin/python3 /opt/ai-core/app/ai-client.py "$@"
BIN_EOF
chmod +x /usr/local/bin/ai-client

cat << 'BIN_EOF' > /usr/local/bin/ai-core-report
#!/usr/bin/env bash
exec /usr/bin/python3 /opt/ai-core/core/report.py "$@"
BIN_EOF
chmod +x /usr/local/bin/ai-core-report

cat << DESK_EOF > "$DESKTOP_DIR/ai-core.desktop"
[Desktop Entry]
Name=AI Core Workspace
Comment=Local AI with 8 MCP services
Exec=ai-client
Icon=system-run-symbolic
Type=Application
Terminal=false
Categories=Development;Utility;
DESK_EOF

# Autostart is OFF by default — an app that relaunches itself
# after every reboot, uninvited, is indistinguishable from a
# pest when it misbehaves (reference laptop, 2026-11-17: crash +
# autostart + session restore stacked copies until it choked).
# To enable it deliberately:
#   cp /usr/share/applications/ai-core.desktop ~/.config/autostart/
echo "🚪 Autostart is off. The app opens when you open it."
echo "   (To start it at login instead: cp /usr/share/applications/ai-core.desktop ~/.config/autostart/)"
chown -R "$REAL_USER":"$REAL_USER" "$TARGET_DIR" 2>/dev/null || true

# --- STEP 8: AUTOMATIC UPDATES ---
# Zak (2026-11-18): 'is there not a way to update the app
# automatically?' Yes: a daily timer runs ai-core-update, which
# pulls the checkout this install came from and re-runs the
# installer ONLY when the pull actually moved (unchanged days
# are a quiet no-op). The installer it re-runs is this one —
# merge mode still protects an owner's Ollama setup. The stamp
# below is how the app itself knows what it is running and can
# offer the same update from its header. Turn it off any time:
#   sudo systemctl disable --now ai-core-update.timer
echo "🔄 Step 8: Automatic updates (daily, only when changed)..."
mkdir -p "$REAL_HOME/.config/ai-core"
cat << STAMP_EOF > "$REAL_HOME/.config/ai-core/installed.json"
{"commit": "$SRC_COMMIT", "src": "$SRC_DIR", "date": "$(date -Iseconds)"}
STAMP_EOF
# Install-time permissions (Zak, 2026-11-18): the app installs
# with full permission or none. AI_CORE_AGREEMENT=all|observer
# in the environment writes the choice into the app's config
# now; unset, the standing choice is kept, and a first run asks
# in the app itself (welcome card, top of the Conduit page).
if [ -n "${AI_CORE_AGREEMENT:-}" ]; then
    python3 - "$REAL_HOME/.config/ai-core/conduit.json" "$AI_CORE_AGREEMENT" <<'AGR_EOF' || true
import json, os, sys
path, level = sys.argv[1], sys.argv[2]
if level not in ("observer", "connected", "all"):
    raise SystemExit(f"unknown agreement level: {level}")
data = {}
if os.path.exists(path):
    try:
        data = json.load(open(path))
    except Exception:
        data = {}
data["agreement"] = level
json.dump(data, open(path, "w"), indent=1)
print(f"   🔐 Install-time agreement: {level}")
AGR_EOF
    chown "$REAL_USER":"$REAL_USER" "$REAL_HOME/.config/ai-core/conduit.json" 2>/dev/null || true
fi
chown "$REAL_USER":"$REAL_USER" "$REAL_HOME/.config/ai-core/installed.json" 2>/dev/null || true
cat << UPD_EOF > /usr/local/bin/ai-core-update
#!/usr/bin/env bash
# AI Core updater — deployed by install.sh. Pulls the checkout
# the app was installed from and re-runs its installer, but
# only when the pull moved: an unchanged day is a quiet no-op.
set -e
cd "$SRC_DIR"
BEFORE=\$(git -c safe.directory="$SRC_DIR" rev-parse HEAD 2>/dev/null || echo none)
git -c safe.directory="$SRC_DIR" pull --ff-only
AFTER=\$(git -c safe.directory="$SRC_DIR" rev-parse HEAD 2>/dev/null || echo none)
if [ "\$BEFORE" = "\$AFTER" ]; then
    echo "AI Core is already current (\$AFTER)."
    exit 0
fi
echo "Updating AI Core: \$BEFORE -> \$AFTER"
exec bash install.sh
UPD_EOF
chmod +x /usr/local/bin/ai-core-update
cat << 'SVC_EOF' > "$SYSTEMD_DIR/ai-core-update.service"
[Unit]
Description=AI Core automatic update (only when the source moved)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/ai-core-update
SVC_EOF
cat << 'TMR_EOF' > "$SYSTEMD_DIR/ai-core-update.timer"
[Unit]
Description=Daily AI Core update check

[Timer]
OnCalendar=daily
RandomizedDelaySec=1800
Persistent=true

[Install]
WantedBy=timers.target
TMR_EOF
systemctl daemon-reload
systemctl enable --now ai-core-update.timer 2>/dev/null || true
echo "   ✅ ai-core-update.timer is on (daily). Off switch:"
echo "      sudo systemctl disable --now ai-core-update.timer"
echo "   The app also checks on launch and offers the update in"
echo "   its header when one is waiting."

# --- VALIDATION ---
echo ""
echo "🔍 Post-install validation..."
ALL_OK=true
for name in "${MCP_NODES[@]}"; do
    if systemctl is-active --quiet "ai-mcp-$name.service"; then
        echo "  ✅ ai-mcp-$name"
    else
        echo "  ❌ ai-mcp-$name (INACTIVE)"
        ALL_OK=false
    fi
done
# The door is part of the verdict, not a footnote: an install whose
# talking model never answered is not a successful install.
if $DOOR_OK; then
    echo "  ✅ model door (Ollama answering)"
else
    echo "  ❌ model door (Ollama NOT answering — install incomplete)"
    ALL_OK=false
fi
if $SEAT_CHECKED; then
    if $SEAT_OK; then
        echo "  ✅ talking model seated (proven in ollama ps)"
    else
        echo "  ❌ talking model NOT seated — install incomplete"
        ALL_OK=false
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if $ALL_OK; then
    echo "✅ AI Core installed successfully!"
elif ! $DOOR_OK; then
    echo "⚠️ AI Core installed — INCOMPLETE: the model door is not running."
    echo "   The app works as an observer; no talking model was installed."
    echo "   Fix Ollama, then re-run this installer — re-running is safe."
elif $SEAT_CHECKED && ! $SEAT_OK; then
    echo "⚠️ AI Core installed — INCOMPLETE: the talking model did not seat."
    echo "   Check free memory (free -h) and: journalctl -u ollama -n 20"
    echo "   Then re-run this installer — re-running is safe."
else
    echo "⚠️ AI Core installed with some inactive services."
    echo "   Check: sudo journalctl -u ai-mcp-* -n 10"
fi
if $DOOR_OK; then
    echo "🚪 Model door: Ollama is answering on localhost:11434."
else
    echo "🚪 Model door: silent. Remedy: sudo systemctl enable --now ollama,"
    echo "   then re-run this installer — it merges and continues safely."
fi
echo ""
echo "📋 Quick reference:"
echo "   Run:   ai-client"
echo "   Logs:  journalctl -u ai-mcp-shell -f"
echo "   MCP:   nc 127.0.0.1 9104 <<< '{\"action\":\"ping\"}'"
echo "   Model: the app checks your shelf on first launch and advises — you decide."
echo "   Uninstall:  sudo ./install.sh uninstall"
echo ""
echo "🤝 Your agreement with this app — three levels, your choice, changeable"
echo "   any time on the Conduit page (it starts at Observer):"
echo "   1. Observer — no permissions granted: chatbot + search assist only."
echo "   2. Connected — local organs: models seat, quick actions and services run."
echo "   3. All — full attachment: shell commands and file operations, deletion"
echo "      included, run locally at your direction."
echo "   Disclaimer for All: that power is the point of the tier and the risk of"
echo "   it. Keep it on only while you want it; dropping back is immediate."
echo ""
echo "💾 Backup suggestion:"
echo "   Timeshift: apt install timeshift && sudo timeshift --create"
echo "   Config:    cp -a /opt/ai-core ~/ai-core-backup"
echo "   Ollama:    cp -a ~/.ollama ~/ollama-backup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if ! $DOOR_OK; then
    echo "🛑 Exiting non-zero: the model door never answered, so this"
    echo "   install is not complete. See the INCOMPLETE note above."
    echo "   Build a failure report to send: ai-core-report"
    exit 1
fi