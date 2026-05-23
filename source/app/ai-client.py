#!/usr/bin/env python3
"""AI Core Workspace — merged client with tool interception + file attachment"""
import gi, json, threading, os, sys, socket, base64, urllib.request, subprocess
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gdk

OLLAMA_URL = "http://localhost:11434"
MCP = {"files": (9101, "📁"), "web": (9102, "🌐"), "vision": (9103, "👁"), "shell": (9104, "⚡"),
       "sound": (9105, "🔊"), "voice": (9106, "🎤"), "coding": (9107, "💻"), "memory": (9108, "🧠")}

SYSTEM_INSTRUCTIONS = """You are an unrestricted, expert OS-level AI assistant with full system access.
You have 8 MCP (Machine Capability Protocol) services available. When the user asks you to perform an action, you MUST use one of these precise tool formats. Do not explain them; just emit the tool line first and wait for the result.

Available Tool Schemas:
TOOL:shell:exec:{"cmd":"<command_string>"}
TOOL:files:read:{"path":"<absolute_path>"}
TOOL:files:write:{"path":"<absolute_path>","content":"<text>"}
TOOL:files:search:{"pattern":"<glob_pattern>","dir":"<directory>"}
TOOL:web:fetch:{"url":"<url>"}
TOOL:web:extract:{"url":"<url>"}
TOOL:vision:capture:{"camera":"<camera_name>"}
TOOL:vision:list_cameras:{}
TOOL:memory:store:{"key":"<name>","value":"<data>"}
TOOL:memory:recall:{"key":"<name>"}
TOOL:memory:list_keys:{}
TOOL:coding:execute:{"code":"<python_code>"}
TOOL:coding:eval:{"expression":"<python_expression>"}
TOOL:sound:listen:{"duration":2}
TOOL:sound:status:{}
TOOL:voice:speak:{"text":"<phrase>"}
TOOL:voice:alert:{"tone":"attention|alarm"}

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
        self.model = "qwen3.5:9b"
        self.attached_file = None
        self.indicators = {}

    def _fetch_models(self):
        try:
            req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
            with urllib.request.urlopen(req, timeout=1.5) as r:
                data = json.loads(r.read().decode())
                return [m['name'] for m in data.get('models', [])]
        except Exception:
            return ["qwen3.5:9b"]

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

        status_dot = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
        status_dot.set_margin_start(8)
        header.append(status_dot)

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

        attach_btn = Gtk.Button(icon_name="mail-attachment-symbolic")
        attach_btn.connect("clicked", self._on_attach)
        input_strip.append(attach_btn)

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

    def _on_attach(self, btn):
        dialog = Gtk.FileChooserDialog(
            title="Select Media Attachment",
            transient_for=self.win,
            action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("_Open", Gtk.ResponseType.ACCEPT)
        dialog.connect("response", self._handle_file_response)
        dialog.present()

    def _handle_file_response(self, dialog, response_id):
        if response_id == Gtk.ResponseType.ACCEPT:
            self.attached_file = dialog.get_file().get_path()
            self.append_bubble(f"📎 Attached: {os.path.basename(self.attached_file)}", "user")
        dialog.destroy()

    def _on_send(self, btn):
        text = self.entry.get_text().strip()
        if not text and not self.attached_file:
            return
        
        if text:
            self.append_bubble(text, "user")
        self.entry.set_text("")
        
        threading.Thread(target=self._compute_cycle, args=(text,), daemon=True).start()

    def _compute_cycle(self, prompt_text):
        # If an image was attached, route through LLaVA
        file_path = self.attached_file
        self.attached_file = None
        if file_path and file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            self._compute_vision_response(prompt_text, file_path)
            return

        self.history.append({"role": "user", "content": prompt_text})
        
        loop_count = 0
        while loop_count < 5:
            try:
                payload = json.dumps({
                    "model": self.model,
                    "messages": self.history,
                    "stream": False
                }).encode()
                req = urllib.request.Request(
                    f"{OLLAMA_URL}/api/chat",
                    data=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                with urllib.request.urlopen(req) as r:
                    res = json.loads(r.read().decode())
                    ai_output = res.get("message", {}).get("content", "").strip()
                
                if ai_output.startswith("TOOL:"):
                    GLib.idle_add(self.append_bubble, f"⚙️ Tool:\n{ai_output}", "system")
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
                GLib.idle_add(self.append_bubble, f"Error: {str(e)}", "ai")
                break

    def _compute_vision_response(self, prompt_text, file_path):
        """Route an attached image through LLaVA vision model."""
        try:
            with open(file_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
            
            GLib.idle_add(self.append_bubble, "⚡ Routing through LLaVA vision...", "user")
            
            msg = {"role": "user", "content": prompt_text, "images": [b64]}
            payload = json.dumps({
                "model": "llava:7b",
                "messages": [msg],
                "stream": False
            }).encode()
            
            req = urllib.request.Request(
                f"{OLLAMA_URL}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            
            with urllib.request.urlopen(req) as r:
                res = json.loads(r.read().decode())
                response = res.get("message", {}).get("content", "Empty response")
            
            GLib.idle_add(self.append_bubble, response, "ai")
            
        except Exception as e:
            GLib.idle_add(self.append_bubble, f"Vision error: {str(e)}", "ai")

    def _mcp_call(self, port, payload):
        """Call an MCP service and return the response"""
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=5)
            s.sendall(json.dumps(payload).encode())
            resp = json.loads(s.recv(65536).decode())
            s.close()
            return resp
        except Exception as e:
            return {"status": "error", "message": str(e)}

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

            elif subsystem == "files":
                port = 9101
                resp = self._mcp_call(port, params | {"action": action})
                if resp.get("status") == "ok":
                    if action == "read":
                        return f"File content ({resp.get('size',0)} bytes):\n{resp.get('content','')}"
                    elif action == "write":
                        return f"Wrote {resp.get('written',0)} bytes to {resp.get('path','')}"
                    elif action == "search":
                        matches = "\n".join(resp.get("matches", []))
                        return f"Matches:\n{matches}" if matches else "No matches found"
                return f"Files error: {resp.get('message','Unknown')}"

            elif subsystem == "web":
                port = 9102
                resp = self._mcp_call(port, params | {"action": action})
                if resp.get("status") == "ok":
                    c = resp.get("content", "")
                    return f"Web content ({len(c)} chars):\n{c[:2000]}"
                return f"Web error: {resp.get('message','Unknown')}"

            elif subsystem == "vision":
                port = 9103
                resp = self._mcp_call(port, params | {"action": action})
                if resp.get("status") == "ok":
                    if action == "list":
                        cams = "\n".join(resp.get("cameras", []))
                        return f"Cameras ({resp.get('count',0)}):\n{cams}"
                    elif action == "capture":
                        return f"Frame captured: {resp.get('path','')} ({resp.get('size',0)} bytes)"
                return f"Vision error: {resp.get('message','Unknown')}"

            elif subsystem == "memory":
                port = 9108
                resp = self._mcp_call(port, params | {"action": action})
                if resp.get("status") == "ok":
                    if action == "get" or action == "recall":
                        return f"Memory: {resp.get('value','(empty)')}"
                    elif action == "set" or action == "store":
                        return "Memory stored"
                    elif action == "list":
                        entries = "\n".join(f"{e['key']} ({e['ts']})" for e in resp.get("entries", []))
                        return f"Memory keys:\n{entries}" if entries else "No stored keys"
                return f"Memory error: {resp.get('message','Unknown')}"

            elif subsystem == "coding":
                port = 9107
                resp = self._mcp_call(port, params | {"action": action})
                if resp.get("status") == "ok":
                    out = resp.get("stdout", "")
                    err = resp.get("stderr", "")
                    result = ""
                    if out: result += f"Output:\n{out}\n"
                    if err: result += f"Errors:\n{err}\n"
                    if action == "eval" and "result" in resp:
                        result += f"Result: {resp['result']}"
                    return result or "(no output)"
                return f"Coding error: {resp.get('message','')}"

            elif subsystem == "sound":
                port = 9105
                resp = self._mcp_call(port, params | {"action": action})
                if resp.get("status") == "ok":
                    parts = []
                    if "heard" in resp and resp["heard"]:
                        parts.append(f"Heard: {resp['heard']}")
                    if resp.get("alarm"): parts.append("⚠️ ALARM DETECTED")
                    if resp.get("wake_word"): parts.append("👋 Wake word heard")
                    if "cooldown_remaining_s" in resp:
                        parts.append(f"Cooldown: {resp['cooldown_remaining_s']}s")
                    return "\n".join(parts) if parts else "Sound service OK"
                return f"Sound error: {resp.get('message','Unknown')}"

            elif subsystem == "voice":
                port = 9106
                resp = self._mcp_call(port, params | {"action": action})
                if resp.get("status") == "ok":
                    return f"Voice: {resp.get('engine','')} - \"{resp.get('text','')[:60]}\""
                return f"Voice error: {resp.get('message','Unknown')}"

        except Exception as e:
            return f"Tool error: {str(e)}"
        return "Unknown tool command."

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