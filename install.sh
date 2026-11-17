#!/usr/bin/env bash
# ======================================================================
# AI Core Framework - Intelligent Hardware-Adapting Advanced Installer
# Includes: uninstall mode, post-install validation, backup guidance
# ======================================================================
set -euo pipefail

TARGET_DIR="/opt/ai-core"
SYSTEMD_DIR="/etc/systemd/system"
DESKTOP_DIR="/usr/share/applications"
MCP_NODES=("files" "web" "vision" "shell" "sound" "voice" "coding" "memory")
# Geometrically nested layout: each service lives in its ring under
# source/rings/ (see docs/GEOMETRIC_NESTING.md). Names/ports unchanged.
declare -A MCP_RING=( [files]=actuation [shell]=actuation [memory]=state [coding]=state [web]=atmosphere [vision]=atmosphere [sound]=atmosphere [voice]=atmosphere )

# --- UNINSTALL ---
if [[ "${1:-}" == "uninstall" ]]; then
    echo "🗑️ Uninstalling AI Core..."
    for name in "${MCP_NODES[@]}"; do
        systemctl stop "ai-mcp-$name.service" 2>/dev/null || true
        systemctl disable "ai-mcp-$name.service" 2>/dev/null || true
        rm -f "$SYSTEMD_DIR/ai-mcp-$name.service"
    done
    rm -f /usr/local/bin/ai-client
    rm -f "$DESKTOP_DIR/ai-core.desktop"
    rm -f "$REAL_HOME/.config/autostart/ai-core.desktop" 2>/dev/null || true
    rm -rf "$TARGET_DIR"
    systemctl daemon-reload
    echo "✅ AI Core uninstalled. /opt/ai-core removed. MCP services stopped."
    echo "💡 Backup tip: Your Ollama models (~/.ollama/) and config were preserved."
    exit 0
fi

# --- PRIVILEGE CHECK ---
if [[ $EUID -ne 0 ]]; then
   echo "⚠️ Administrative privileges required. Re-routing via sudo..."
   exec sudo bash "$0" "$@"
fi

REAL_USER="${SUDO_USER:-$(logname 2>/dev/null || echo "$USER")}"
REAL_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)

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

echo "🧠 Step 2: Auditing system resources..."
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
TOTAL_RAM_GB=$(( TOTAL_RAM_KB / 1024 / 1024 ))
echo "📊 Detected RAM: ${TOTAL_RAM_GB}GB"

if [ "$TOTAL_RAM_GB" -ge 16 ]; then
    OPTIMAL_MODEL="qwen3.5:9b"
    echo "✅ Selected: $OPTIMAL_MODEL"
else
    OPTIMAL_MODEL="qwen3:8b"
    echo "⚠️ Limited memory: $OPTIMAL_MODEL"
fi

echo "🎮 Step 3: GPU detection..."
GPU_VENDOR="CPU"
if lspci | grep -qi "nvidia"; then GPU_VENDOR="NVIDIA"; echo "🚀 NVIDIA GPU"
elif lspci | grep -qi "amd\|ati"; then GPU_VENDOR="AMD"; echo "🔮 AMD GPU"
fi

echo "🦙 Step 4: Ollama setup..."
if ! command -v ollama &>/dev/null; then
    echo "📥 Installing Ollama..."
    su - "$REAL_USER" -c "curl -fsSL https://ollama.com/install.sh | sh" || true
fi

mkdir -p /etc/systemd/system/ollama.service.d/
cat << OLL_ENV_EOF > /etc/systemd/system/ollama.service.d/override.conf
[Service]
Environment="OLLAMA_NUM_PARALLEL=2"
Environment="OLLAMA_KEEP_ALIVE=-1"
OLL_ENV_EOF

if [ "$GPU_VENDOR" = "NVIDIA" ]; then
    echo 'Environment="CUDA_VISIBLE_DEVICES=0"' >> /etc/systemd/system/ollama.service.d/override.conf
elif [ "$GPU_VENDOR" = "AMD" ]; then
    echo 'Environment="HSA_OVERRIDE_GFX_VERSION=10.3.0"' >> /etc/systemd/system/ollama.service.d/override.conf
fi

systemctl daemon-reload
systemctl enable ollama.service --now || true
systemctl restart ollama.service || true
sleep 3

# Validate Ollama
if curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    echo "✅ Ollama API responding"
    su - "$REAL_USER" -c "ollama pull $OPTIMAL_MODEL 2>/dev/null" || echo "⚠️ Model pull deferred (run: ollama pull $OPTIMAL_MODEL)"
else
    echo "⚠️ Ollama not responding. Install may need manual intervention."
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
    python3 - "$CRAWL_DIR" "$OPTIMAL_MODEL" <<'CRAWL_EOF'
import json, os, sys
d, optimal = sys.argv[1], sys.argv[2]
c = json.load(open(os.path.join(d, "expectations.json")))
p = json.load(open(os.path.join(d, "pipes.json")))
exp = c["expectations"]; tiers = {t["tier"]: t for t in exp["tiers"]}
print(f"   🖥️  {c['host']}: {c['cpu']['effective_threads']} effective threads, "
      f"{round(c['ram']['effective_mb']/1024, 1)} GB usable RAM, "
      f"{('GPU: ' + ', '.join(g['name'] for g in c['gpus'])) if c['gpus'] else 'no GPU'}")
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

sed -i "s/self.model = \"qwen3.5:9b\"/self.model = \"$OPTIMAL_MODEL\"/g" "$TARGET_DIR/app/ai-client.py"
sed -i "s/return \[\".*:9b\"\]/return [\"$OPTIMAL_MODEL\"]/g" "$TARGET_DIR/app/ai-client.py"

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

mkdir -p "$REAL_HOME/.config/autostart"
cp "$DESKTOP_DIR/ai-core.desktop" "$REAL_HOME/.config/autostart/" 2>/dev/null || true
chown -R "$REAL_USER":"$REAL_USER" "$TARGET_DIR" "$REAL_HOME/.config/autostart" 2>/dev/null || true

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

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if $ALL_OK; then
    echo "✅ AI Core installed successfully!"
else
    echo "⚠️ AI Core installed with some inactive services."
    echo "   Check: sudo journalctl -u ai-mcp-* -n 10"
fi
if curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    echo "🚪 Model door: Ollama is answering on localhost:11434."
else
    echo "🚪 Model door: Ollama is NOT answering yet. The app will greet you"
    echo "   with the remedy on its landing page (start it with:"
    echo "   sudo systemctl enable --now ollama)."
fi
echo ""
echo "📋 Quick reference:"
echo "   Run:   ai-client"
echo "   Logs:  journalctl -u ai-mcp-shell -f"
echo "   MCP:   nc 127.0.0.1 9104 <<< '{\"action\":\"ping\"}'"
echo "   Pull model: ollama pull $OPTIMAL_MODEL"
echo "   Uninstall:  sudo ./install.sh uninstall"
echo ""
echo "💾 Backup suggestion:"
echo "   Timeshift: apt install timeshift && sudo timeshift --create"
echo "   Config:    cp -a /opt/ai-core ~/ai-core-backup"
echo "   Ollama:    cp -a ~/.ollama ~/ollama-backup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"