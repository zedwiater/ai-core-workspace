#!/usr/bin/env python3
"""George's MCP Files Service — read/write/search files via TCP"""
import socket, json, os, glob

HOST = '127.0.0.1'
PORT = 9101

def handle(data):
    try:
        req = json.loads(data)
        a = req.get("action", "ping")
        if a == "ping": return {"status": "pong"}
        if a == "read":
            p = req.get("path","")
            if not os.path.exists(p): return {"status":"error","message":"Not found"}
            with open(p, 'r', errors='ignore') as f: c = f.read(10000)
            return {"status":"ok","path":p,"size":len(c),"content":c[:5000]}
        if a == "write":
            p = req.get("path",""); c = req.get("content","")
            os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
            with open(p, 'w') as f: f.write(c)
            return {"status":"ok","path":p,"written":len(c)}
        if a == "search":
            p = req.get("pattern",""); d = req.get("dir","/tmp")
            r = glob.glob(f"{d}/**/{p}", recursive=True)[:20]
            return {"status":"ok","matches":r}
        return {"status":"error","message":f"Unknown action: {a}"}
    except Exception as e:
        return {"status":"error","message":str(e)}

s = socket.socket(); s.setsockopt(1,2,1); s.bind((HOST,PORT)); s.listen(5)
while True:
    try:
        c,a = s.accept(); d = c.recv(65536)
        if d: c.sendall(json.dumps(handle(d.decode())).encode())
        c.close()
    except: pass