# 🚀 AI Core Workspace Engine

AI Core Workspace is a lightweight, low-latency, multi-node automation framework designed to connect local Large Language Models (LLMs) directly to OS-level system utilities. Built using **Python 3**, **GTK4/Libadwaita**, and **Systemd**, this application transforms an LLM into an active system operator capable of executing shell commands, analyzing local files, and communicating over modular micro-services.

The framework utilizes a continuous **Intercept & Compute Cycle**. When a user types a command, the prompt is parsed by a local Ollama instance. If the model requires system interactions, it emits a structured tool execution token which is captured, handled safely by the host client, and fed back into the conversation context seamlessly.

---

## 🏗️ System Architecture & Framework Layout

The project splits resource handling across 8 decoupled, ultra-lightweight system background socket nodes acting as an abstraction layer for Model Context Protocol (MCP) interactions:

* **⚡ Shell (\`mcp-shell.py\`)**: Handles low-level terminal command invocation (\`exec\`).
* **📁 Files (\`mcp-files.py\`)**: Intercepts file system context requests and streams target reads safely.
* **🧠 Memory (\`mcp-memory.py\`)**: Manages long-term state across independent execution loops.
* **🌐 Web (\`mcp-web.py\`) / 👁️ Vision (\`mcp-vision.py\`)**: Pipeline vectors for live internet routing and image matrix parsing.
* **🔊 Sound / 🎤 Voice / 💻 Coding**: Auxiliary hooks for real-time environment automation.

---

## 📦 Universal Distribution Package Structure

The repository is organized cleanly to allow effortless distribution or compilation across multiple Linux distributions (Ubuntu/Debian, Fedora, Arch Linux):

\`\`\`text
├── install.sh                               # Multi-distro dependency & setup wrapper
├── README.md                                # Project landing page & technical documentation
├── ai_core_distro_install_instructions.png  # Graphic onboarding map
└── source/
    ├── app/
    │   └── ai-client.py                     # Main GTK4 multi-threaded client application
    └── mcp/
        └── mcp-*.py                         # The 8 background micro-service socket loops
\`\`\`

---

## 🚀 Quickstart Installation

Anyone can deploy this framework globally to their Linux system with a single execution flow.

### 1. Clone or Download the Bundle
Extract the release tarball or clone the repository directly:
\`\`\`bash
git clone https://github.com/YOUR_USERNAME/ai-core-workspace.git
cd ai-core-workspace
\`\`\`

### 2. Execute the Master Installer
Run the universal automation script to satisfy system runtimes (PyGObject, GTK4, Cairo), compile systemd daemons, register command-line symbols, and create application entries:
\`\`\`bash
sudo ./install.sh
\`\`\`

### 3. Initialize Workspace
Launch the application panel natively from your distribution launcher application menu or spin it directly from the terminal shell:
\`\`\`bash
ai-client
\`\`\`

---

## 🛠️ Operational Capability Highlights

* **Dynamic Model Interrogator**: Queries your local Ollama server instance (\`/api/tags\`) automatically at runtime to populate a clean selection menu.
* **Visual Status Micro-mesh**: Continually polls local service sockets asynchronously every 2.5 seconds to accurately reflect background node availability using colorized frontend GTK indicator nodes.
* **Self-Healing Services**: Systemd process management profiles keep all backend execution sockets alive with instantaneous auto-restart policies.

---
*Developed as an open-source framework for secure, local system management automation.*
