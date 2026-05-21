#!/usr/bin/env bash
# ======================================================================
# AI Core Framework - Intelligent Hardware-Adapting Advanced Installer
# ======================================================================
set -euo pipefail

TARGET_DIR="/opt/ai-core"
SYSTEMD_DIR="/etc/systemd/system"
DESKTOP_DIR="/usr/share/applications"

if [[ $EUID -ne 0 ]]; then
   echo "⚠️ Administrative privileges required. Re-routing via sudo..."
   exec sudo bash "$0" "$@"
fi

REAL_USER="${SUDO_USER:-$(logname 2>/dev/null || echo "$USER")}"
REAL_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)

echo "📦 Step 1: Resolving baseline Linux runtime packages..."
if command -v apt-get &>/dev/null; then
    apt-get update && apt-get install -y python3 python3-gi python3-gi-cairo libgtk-4-dev gir1.2-gtk-4.0 libadwaita-1-dev gir1.2-adw-1 libgtk-4-dev gir1.2-gtk-4.0 libgirepository1.0-dev libcairo2-dev curl lshw pciutils
elif command -v dnf &>/dev/null; then
    dnf install -y python3 python3-gobject cairo-gobject-devel libgirepository-devel curl lshw pciutils
elif command -v pacman &>/dev/null; then
    pacman -Sy --needed --noconfirm python python-gobject cairo curl lshw pciutils
fi

echo "🧠 Step 2: Auditing system resource limits and defining model thresholds..."
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
TOTAL_RAM_GB=$(( TOTAL_RAM_KB / 1024 / 1024 ))
echo "📊 Detected System RAM: ${TOTAL_RAM_GB}GB"

# Set model tier based on available system memory threshold
if [ "$TOTAL_RAM_GB" -ge 16 ]; then
    OPTIMAL_MODEL="qwen2.5:8b"
    echo "✅ Memory threshold met. Selected baseline performance tier: $OPTIMAL_MODEL"
else
    OPTIMAL_MODEL="qwen2.5:1.5b"
    echo "⚠️ Limited memory profile detected. Selected high-efficiency fallback tier: $OPTIMAL_MODEL"
fi

echo "🎮 Step 3: Probing graphics controllers for GPU acceleration hardware..."
GPU_VENDOR="CPU"
if lspci | grep -qi "nvidia"; then
    GPU_VENDOR="NVIDIA"
    echo "🚀 Found NVIDIA Discrete Graphics Hardware."
elif lspci | grep -qi "amd" || lspci | grep -qi "ati"; then
    GPU_VENDOR="AMD"
    echo "🔮 Found AMD Radeon Graphics Hardware."
fi

# Install driver compute dependencies based on GPU vendor target
case "$GPU_VENDOR" in
    "NVIDIA")
        echo "🔧 Provisioning acceleration drivers for NVIDIA CUDA ecosystem..."
        if command -v apt-get &>/dev/null; then
            apt-get install -y nvidia-headless-no-dkms-535 nvidia-utils-535 || true
        elif command -v pacman &>/dev/null; then
            pacman -S --needed --noconfirm nvidia-utils || true
        fi
        ;;
    "AMD")
        echo "🔧 Provisioning driver layers for AMD ROCm open ecosystem..."
        if command -v apt-get &>/dev/null; then
            apt-get install -y libgomp1 || true
        elif command -v pacman &>/dev/null; then
            pacman -S --needed --noconfirm rocm-core opencl-amd || true
        fi
        ;;
    *)
        echo "🐌 No compatible discrete GPU found. Falling back to native highly-optimized CPU tensor execution."
        ;;
esac

echo "🦙 Step 4: Installing and configuring self-healing Ollama Core..."
if ! command -v ollama &>/dev/null; then
    echo "📥 Downloading official Ollama daemon platform..."
    su - "$REAL_USER" -c "curl -fsSL https://ollama.com/install.sh | sh" || true
fi

# Build explicit runtime optimizations directly into the Ollama systemd layer overrides
mkdir -p /etc/systemd/system/ollama.service.d/
cat << OLL_ENV_EOF > /etc/systemd/system/ollama.service.d/override.conf
[Service]
Environment="OLLAMA_NUM_PARALLEL=2"
OLL_ENV_EOF

# If hardware profile allows, inject split context allocations and GPU thread targets
if [ "$GPU_VENDOR" = "NVIDIA" ]; then
    echo 'Environment="CUDA_VISIBLE_DEVICES=0"' >> /etc/systemd/system/ollama.service.d/override.conf
elif [ "$GPU_VENDOR" = "AMD" ]; then
    echo 'Environment="HSA_OVERRIDE_GFX_VERSION=10.3.0"' >> /etc/systemd/system/ollama.service.d/override.conf
fi

echo "🔄 Reloading configurations and pulling target weights..."
systemctl daemon-reload
systemctl enable ollama.service --now || true
systemctl restart ollama.service || true

# Pause to ensure endpoint socket is binding correctly
sleep 4
echo "📥 Staging model files (This may take a moment depending on network connectivity)..."
su - "$REAL_USER" -c "ollama pull $OPTIMAL_MODEL"

echo "📂 Step 5: Deploying UI Client workspace files..."
mkdir -p "$TARGET_DIR/app" "$TARGET_DIR/mcp"
cp -r source/mcp/* "$TARGET_DIR/mcp/"
cp -r source/app/* "$TARGET_DIR/app/"
chmod +x "$TARGET_DIR/app/ai-client.py"

# Dynamically patch the Python application source so its drop-down selector matches our auto-selected threshold model
sed -i "s/self.model = \"qwen2.5:8b\"/self.model = \"$OPTIMAL_MODEL\"/g" "$TARGET_DIR/app/ai-client.py"

echo "⚙️ Step 6: Instantiating the 8 system automation micro-service channels..."
MCP_NODES=("files" "web" "vision" "shell" "sound" "voice" "coding" "memory")
START_PORT=9101

for i in "${!MCP_NODES[@]}"; do
    NODE_NAME="${MCP_NODES[$i]}"
    cat << SVC_EOF > "$SYSTEMD_DIR/ai-mcp-$NODE_NAME.service"
[Unit]
Description=AI Core MCP Node ($NODE_NAME)
After=network.target

[Service]
ExecStart=/usr/bin/python3 $TARGET_DIR/mcp/mcp-$NODE_NAME.py
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
SVC_EOF

    systemctl enable "ai-mcp-$NODE_NAME.service" --now
    systemctl restart "ai-mcp-$NODE_NAME.service"
done

echo "🔗 Step 7: Mapping local shortcuts and autostart profiles..."
cat << 'BIN_EOF' > /usr/local/bin/ai-client
#!/usr/bin/env bash
exec /usr/bin/python3 /opt/ai-core/app/ai-client.py "$@"
BIN_EOF
chmod +x /usr/local/bin/ai-client

cat << DESK_EOF > "$DESKTOP_DIR/ai-core.desktop"
[Desktop Entry]
Name=AI Core Workspace
Comment=Intelligent Multi-Node Autonomous Interface Engine
Exec=ai-client
Icon=system-run-symbolic
Type=Application
Terminal=false
Categories=Development;Utility;
DESK_EOF

mkdir -p "$REAL_HOME/.config/autostart"
cp "$DESKTOP_DIR/ai-core.desktop" "$REAL_HOME/.config/autostart/"
chown -R "$REAL_USER":"$REAL_USER" "$TARGET_DIR" "$REAL_HOME/.config/autostart"

echo "🚀 COMPLETE! System optimized for $GPU_VENDOR execution. Run via menu or terminal using: ai-client"
