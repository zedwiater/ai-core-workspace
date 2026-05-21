cat << 'EOF' > ~/ai-core-dist/install.sh
#!/usr/bin/env bash
# ======================================================================
# AI Core Framework - Universal Multi-Node Installer
# ======================================================================
set -euo pipefail

TARGET_DIR="/opt/ai-core"
SYSTEMD_DIR="/etc/systemd/system"
DESKTOP_DIR="/usr/share/applications"

# Force root execution for system layouts
if [[ $EUID -ne 0 ]]; then
   echo "⚠️ This installer requires administrative privileges. Re-routing via sudo..."
   exec sudo bash "$0" "$@"
fi

# Track the non-root interactive user context
REAL_USER="${SUDO_USER:-$(logname 2>/dev/null || echo "$USER")}"
REAL_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)

echo "📦 Step 1: Identifying environment and resolving system packages..."
if command -v apt-get &>/dev/null; then
    apt-get update
    apt-get install -y python3 python3-gi python3-gi-cairo libgirepository1.0-dev libcairo2-dev curl
elif command -v dnf &>/dev/null; then
    dnf install -y python3 python3-gobject cairo-gobject-devel libgirepository-devel curl
elif command -v pacman &>/dev/null; then
    pacman -Sy --needed --noconfirm python python-gobject cairo curl
else
    echo "⚠️ Unknown package manager. Please ensure GTK4 and PyGObject runtimes are present."
fi

echo "📂 Step 2: Deploying framework assets into structural locations..."
mkdir -p "$TARGET_DIR/app" "$TARGET_DIR/mcp"
cp -r source/mcp/* "$TARGET_DIR/mcp/"
cp -r source/app/* "$TARGET_DIR/app/"
chmod +x "$TARGET_DIR/app/ai-client.py"

echo "⚙️ Step 3: Registering and mounting system micro-services..."
MCP_NODES=("files" "web" "vision" "shell" "sound" "voice" "coding" "memory")
START_PORT=9101

for i in "${!MCP_NODES[@]}"; do
    NODE_NAME="${MCP_NODES[$i]}"
    
    # Generate clean, explicit systemd service files dynamically
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

echo "🔗 Step 4: Exposing command wrappers to the system binary PATH..."
cat << 'BIN_EOF' > /usr/local/bin/ai-client
#!/usr/bin/env bash
exec /usr/bin/python3 /opt/ai-core/app/ai-client.py "$@"
BIN_EOF
chmod +x /usr/local/bin/ai-client

echo "🖥️ Step 5: Constructing Desktop entries for application menus..."
cat << DESK_EOF > "$DESKTOP_DIR/ai-core.desktop"
[Desktop Entry]
Name=AI Core Workspace
Comment=Unrestricted AI Multi-Node Execution Engine
Exec=ai-client
Icon=system-run-symbolic
Type=Application
Terminal=false
Categories=Development;Utility;
DESK_EOF

# Ensure application launches natively on next user login
mkdir -p "$REAL_HOME/.config/autostart"
cp "$DESKTOP_DIR/ai-core.desktop" "$REAL_HOME/.config/autostart/"

# Correct explicit folder owner permissions
chown -R "$REAL_USER":"$REAL_USER" "$TARGET_DIR"
chown -R "$REAL_USER":"$REAL_USER" "$REAL_HOME/.config/autostart"

echo "🚀 System integration completed successfully! Type 'ai-client' or use your Application Menu to launch."
EOF

# Ensure the installer script itself is runnable
chmod +x ~/ai-core-dist/install.sh
