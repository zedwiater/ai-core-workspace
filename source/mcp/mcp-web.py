#!/usr/bin/env python3
"""George's MCP Web Service — fetch URLs + extract text via TCP"""
import socket, json, urllib.request, html.parser

HOST = '127.0.0.1'
PORT = 9102

class TextExtractor(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
    def handle_data(self, data):
        t = data.strip()
        if t: self.text.append(t)

def handle(data):
    try:
        req = json.loads(data); a = req.get("action","ping")
        if a == "ping": return {"status":"pong"}
        if a == "fetch":
            url = req.get("url","")
            r = urllib.request.urlopen(url, timeout=10)
            raw = r.read().decode(errors='replace')
            return {"status":"ok","content":raw[:5000],"code":r.status}
        if a == "extract":
            url = req.get("url","")
            r = urllib.request.urlopen(url, timeout=10)
            raw = r.read().decode(errors='replace')
            ex = TextExtractor(); ex.feed(raw)
            return {"status":"ok","content":" ".join(ex.text)[:5000],"code":r.status}
        if a == "health":
            r = urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=5)
            return {"status":"ok","reachable":r.status==200,"code":r.status}
        return {"status":"error","message":f"Unknown: {a}"}
    except Exception as e:
        return {"status":"error","message":str(e)}

s = socket.socket(); s.setsockopt(1,2,1); s.bind((HOST,PORT)); s.listen(5)
while True:
    try:
        c,a = s.accept(); d = c.recv(65536)
        if d: c.sendall(json.dumps(handle(d.decode())).encode())
        c.close()
    except: pass