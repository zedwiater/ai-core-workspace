# 🚀 AI Core Workspace Engine

AI Core Workspace is a lightweight, low-latency, multi-node automation framework designed to connect local Large Language Models (LLMs) directly to OS-level system utilities. Built using **Python 3**, **GTK4/Libadwaita**, and **Systemd**, this application transforms an LLM into an active system operator capable of executing shell commands, analyzing local files, and communicating over modular micro-services.

The framework utilizes a continuous **Intercept & Compute Cycle**. When a user types a command, the prompt is parsed by a local Ollama instance. If the model requires system interactions, it emits a structured tool execution token which is captured, handled safely by the host client, and fed back into the conversation context seamlessly.

---

## 🧠 Intelligent, Hardware-Adaptive Installation Architecture

Unlike static installation scripts, this project features a smart deployment engine (`install.sh`) that dynamically inspects your host machine's hardware topology to configure an optimized runtime environment:

* **Dynamic Memory Thresholding**: The installer audits total available system RAM ($M_{total}$). If the system has 16GB or more, it automatically pulls and targets the high-capability **Qwen 3.5 8B** model. On memory-constrained setups (<16GB), it intelligently transitions to an ultra-efficient **Qwen 3.5 1.5B** fallback layer to maximize token velocity and prevent Out-Of-Memory (OOM) crashing.
* **Automated GPU Compute Detection**: The installation layer probes the PCI bus (`lspci`) for discrete hardware graphics accelerators. 
  * **NVIDIA Ecosystem**: Automatically configures support hooks and provisions standard compute utilities if applicable.
  * **AMD Radeon Ecosystem**: Sets up ROCm open-ecosystem compatibility variables.
  * **CPU Fallback**: Optimizes CPU execution threads if a dedicated graphics unit is missing.
* **Orchestration Tuning & VRAM Splitting**: The installer injects hardware-specific execution configurations directly into a customized Systemd override layer (`/etc/systemd/system/ollama.service.d/override.conf`). This sets variables like `OLLAMA_NUM_PARALLEL` and pins device environment flags (`CUDA_VISIBLE_DEVICES` or `HSA_OVERRIDE_GFX_VERSION`) to ensure seamless VRAM loading and hardware layer offloading.

---

## 🏗️ System Architecture & Framework Layout

The project splits resource handling across 8 decoupled, ultra-lightweight system background socket nodes acting as an abstraction layer for Model Context Protocol (MCP) interactions:

* **⚡ Shell (`mcp-shell.py`)**: Handles low-level terminal command invocation (`exec`).
* **📁 Files (`mcp-files.py`)**: Intercepts file system context requests and streams target reads safely.
* **🧠 Memory (`mcp-memory.py`)**: Manages long-term state across independent execution loops.
* **🌐 Web (`mcp-web.py`) / 👁️ Vision (`mcp-vision.py`)**: Pipeline vectors for live internet routing and image matrix parsing.
* **🔊 Sound / 🎤 Voice / 💻 Coding**: Auxiliary hooks for real-time environment automation.

---

---

## 📸 Core Architecture & Live Telemetry Profiles

The following interface captures trace the development milestone from initial source consolidation on the primary workstation to full, resource-constrained edge execution.

### 1. Hardware-Aware Edge Profiling & Daemon Setup
An active look at the terminal environment during a cold installation on edge hardware. The deployment architecture successfully audits system memory thresholds, provisions user rendering permissions, and builds the localized execution layer completely on a CPU fallback layout.

![Automated Hardware Auditing and Systemd Deployment Execution](resource_chrome.png)

### 2. Asynchronous Modern GTK4 Graphic Core Window
The operational, multi-threaded frontend engine executing natively. The interface leverages localized asynchronous socket pooling to continually display real-time micro-mesh states for active background tool-handling routines.

![Active Core Application Interface Framework Rendering](glazing_chromebook_success.png)

### 3. Live Tool Intercept Loop & Process Parsing
Telemetry demonstrating the edge model successfully catching a system operational intent token. The 1.5B resource layer executes a localized shell script call (`ps aux --sort=-%cpu`) to pull host metrics and return an analytical process breakdown without starving system memory registers.

![Context Execution Trace and Active CPU Resource Handling Map](functional_chrome.png)

## 📦 Universal Distribution Package Structure

```text
├── install.sh                               # Intelligent, hardware-adaptive setup engine
├── README.md                                # Project landing page & technical documentation
├── ai_core_distro_install_instructions.png  # Graphic onboarding map
└── source/
    ├── app/
    │   └── ai-client.py                     # Main GTK4 multi-threaded client application
    └── mcp/
        └── mcp-*.py                         # The 8 background micro-service socket loops
