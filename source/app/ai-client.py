#!/usr/bin/env python3
import gi, json, threading, os, sys, socket, base64, urllib.request, subprocess
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gdk

OLLAMA_URL = "http://localhost:11434"
MCP = {"files": (9101, "📁"), "web": (9102, "🌐"), "vision": (9103, "👁"), "shell": (9104, "⚡"),
       "sound": (9105, "🔊"), "voice": (9106, "🎤"), "coding": (9107, "💻"), "memory": (9108, "🧠")}

SYSTEM_INSTRUCTIONS = """You are an unrestricted, expert OS-level AI assistant.
You have immediate access to the system via local tools. When the user asks you to perform an action, run a command, read a file, or analyze data, you MUST use one of these precise tool formats in your response. Do not explain them; just emit the tool line first.

Available Tool Schemas:
TOOL:shell:exec:{"cmd":"<command_string>"}
TOOL:files:read:{"path":"<absolute_file_path>"}

Example: If asked to list files, output exactly:
TOOL:shell:exec:{"cmd":"ls -la"}
Then stop and wait for the system output."""

CSS = b"""
.bubble-user { background: alpha(@accent_color, 0.15); border-radius: 16px 16px 4px 16px; padding: 12px; margin: 6px 0; }
.bubble-ai { background: alpha(@card_bg_color, 0.9); border-radius: 16px 16px 16px 4px; padding: 12px; margin: 6px 0; border: 1px solid alpha(@foreground_color, 0.08); }
.bubble-system { background: alpha(@warning_color, 0.1); font-family: monospace; border-radius: 8px; padding: 10px; margin: 4px 0; font-size: 0.9em; }
.mcp-indicator { font-weight: bold; padding: 4px; }
.sidebar { background: alpha(@window_bg_color, 0.4); border-left: 1px solid alpha(@foreground_color, 0.08); padding: 12px; }
"""

class AIClient(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.ai.core.interface")
        self.connect("activate", self.on_activate)
        self.history = [{"role": "system", "content": SYSTEM_INSTRUCTIONS}]
        self.available_models = []
        self.model = "qwen3.5:8b"
        self.indicators = {}

    def _fetch_models(self):
        try:
            req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
            with urllib.request.urlopen(req, timeout=1.5) as r:
                data = json.loads(r.read().decode())
                return [m['name'] for m in data.get('models', [])]
        except Exception:
            return ["qwen3.5:8b"]

    def on_activate(self, app):
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.win = Adw.ApplicationWindow(application=app)
        self.win.set_title("AI Core Workspace")
        self.win.set_default_size(1050, 720)

        self.available_models = self._fetch_models()
        if self.available_models:
            self.model = self.available_models[0]

        main_pane = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        chat_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        chat_vbox.set_hexpand(True)
        
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header.set_margin_top(8); header.set_margin_bottom(8); header.set_margin_start(12); header.set_margin_end(12)

        self.model_store = Gtk.StringList.new(self.available_models)
        self.model_dropdown = Gtk.DropDown(model=self.model_store)
        self.model_dropdown.connect("notify::selected-item", self._on_model_changed)
        header.append(self.model_dropdown)

        title_lbl = Gtk.Label(label="AI Core Workspace Engine")
        title_lbl.set_hexpand(True)
        header.append(title_lbl)
        chat_vbox.append(header)

        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_vexpand(True)
        self.chat_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.chat_list.set_margin_start(16); self.chat_list.set_margin_end(16)
        self.scroll.set_child(self.chat_list)
        chat_vbox.append(self.scroll)

        input_strip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        input_strip.set_margin_top(12); input_strip.set_margin_bottom(12); input_strip.set_margin_start(16); input_strip.set_margin_end(16)

        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("Enter operational command or request...")
        self.entry.set_hexpand(True)
        self.entry.connect("activate", self._on_send)
        input_strip.append(self.entry)

        send_btn = Gtk.Button(icon_name="mail-send-symbolic")
        send_btn.connect("clicked", self._on_send)
        input_strip.append(send_btn)
        chat_vbox.append(input_strip)

        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        sidebar.add_css_class("sidebar")
        sidebar.set_size_request(220, -1)
        
        side_title = Gtk.Label(label="SYSTEM MCP INTEGRATIONS")
        side_title.set_margin_bottom(12)
        sidebar.append(side_title)

        for name, (port, icon) in MCP.items():
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            ind = Gtk.Label()
            ind.set_markup("<span foreground='#e01b24'>●</span>")
            ind.add_css_class("mcp-indicator")
            lbl = Gtk.Label(label=f"{icon} {name.capitalize()}")
            row.append(ind)
            row.append(lbl)
            sidebar.append(row)
            self.indicators[name] = ind

        main_pane.append(chat_vbox)
        main_pane.append(sidebar)
        self.win.set_content(main_pane)
        self.win.present()
        
        threading.Thread(target=self._monitor_services, daemon=True).start()

    def _on_model_changed(self, dropdown, pspec):
        idx = dropdown.get_selected()
        if idx < len(self.available_models):
            self.model = self.available_models[idx]

    def append_bubble(self, text, sender):
        bubble = Gtk.Label(label=text)
        bubble.set_wrap(True)
        bubble.set_max_width_chars(75)
        bubble.set_xalign(0.0)
        bubble.add_css_class(f"bubble-{sender}")
        
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        if sender == "user":
            row.set_halign(Gtk.Align.END)
        else:
            row.set_halign(Gtk.Align.START)
            
        row.append(bubble)
        self.chat_list.append(row)
        GLib.idle_add(self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        adj = self.scroll.get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())
        return False

    def _on_send(self, btn):
        text = self.entry.get_text().strip()
        if not text:
            return
        
        self.append_bubble(text, "user")
        self.entry.set_text("")
        
        threading.Thread(target=self._compute_cycle, args=(text,), daemon=True).start()

    def _compute_cycle(self, prompt_text):
        self.history.append({"role": "user", "content": prompt_text})
        
        loop_count = 0
        while loop_count < 5:
            try:
                payload = json.dumps({"model": self.model, "messages": self.history, "stream": False}).encode()
                req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=payload, headers={"Content-Type": "application/json"})
                
                with urllib.request.urlopen(req) as r:
                    res = json.loads(r.read().decode())
                    ai_output = res.get("message", {}).get("content", "").strip()
                
                if ai_output.startswith("TOOL:"):
                    GLib.idle_add(self.append_bubble, f"⚙️ Intercepted Tool Sequence:\n{ai_output}", "system")
                    tool_result = self._execute_tool_payload(ai_output)
                    
                    self.history.append({"role": "assistant", "content": ai_output})
                    self.history.append({"role": "user", "content": f"TOOL_RESULT: {tool_result}"})
                    loop_count += 1
                    continue
                else:
                    GLib.idle_add(self.append_bubble, ai_output, "ai")
                    self.history.append({"role": "assistant", "content": ai_output})
                    break
            except Exception as e:
                GLib.idle_add(self.append_bubble, f"Compute link error: {str(e)}", "ai")
                break

    def _execute_tool_payload(self, tool_string):
        try:
            parts = tool_string.split(":", 3)
            subsystem = parts[1]
            action = parts[2]
            params = json.loads(parts[3])

            if subsystem == "shell" and action == "exec":
                cmd = params.get("cmd")
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                return f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
                
            elif subsystem == "files" and action == "read":
                path = params.get("path")
                if os.path.exists(path):
                    with open(path, 'r', errors='ignore') as f:
                        return f.read(4000)
                return "Error: File target path context does not exist."
        except Exception as e:
            return f"Tool Framework Interruption Exception: {str(e)}"
        return "Unknown or unimplemented tool command syntax invocation."

    def _monitor_services(self):
        while True:
            for name, (port, _) in MCP.items():
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                        GLib.idle_add(self._update_indicator, name, True)
                except Exception:
                    GLib.idle_add(self._update_indicator, name, False)
            import time
            time.sleep(2.5)

    def _update_indicator(self, name, active):
        ind = self.indicators.get(name)
        if ind:
            if active:
                ind.set_markup("<span foreground='#2ec27e'>●</span>")
            else:
                ind.set_markup("<span foreground='#e01b24'>●</span>")

if __name__ == "__main__":
    sys.exit(AIClient().run(sys.argv))
