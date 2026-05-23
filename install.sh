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
    dnf install -y python3 python3-gobject cairo-gobject-devel libgirepository-devel curl lshw pciutils ffmpeg
elif command -v pacman &>/dev/null; then
    pacman -Sy --needed --noconfirm python python-gobject cairo curl lshw pciutils ffmpeg
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

echo "📂 Step 5: Deploying files..."
mkdir -p "$TARGET_DIR/app" "$TARGET_DIR/mcp"
cp -r source/mcp/* "$TARGET_DIR/mcp/"
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
ExecStart=/usr/bin/python3 $TARGET_DIR/mcp/mcp-$name.py
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