#!/usr/bin/env python3
"""George's MCP Memory Service — persistent key-value store"""
import socket, json, sqlite3, os

HOST = '127.0.0.1'; PORT = 9108
DB = "/opt/ai-core/george_memory.db"

def init():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB); c.execute("CREATE TABLE IF NOT EXISTS mem (key TEXT PRIMARY KEY, val TEXT, ts TEXT)")
    c.commit(); c.close()

def handle(data):
    try:
        req = json.loads(data); a = req.get("action","ping")
        if a == "ping": return {"status":"pong"}
        c = sqlite3.connect(DB)
        if a == "get":
            r = c.execute("SELECT val FROM mem WHERE key=?", (req["key"],)).fetchone()
            return {"status":"ok","value":r[0] if r else None}
        if a == "set":
            c.execute("REPLACE INTO mem VALUES (?,?,datetime('now'))", (req["key"], req["value"])); c.commit()
            return {"status":"ok"}
        if a == "list":
            r = c.execute("SELECT key, ts FROM mem ORDER BY ts DESC LIMIT 50").fetchall()
            return {"status":"ok","entries":[{"key":k,"ts":t} for k,t in r]}
        if a == "delete":
            c.execute("DELETE FROM mem WHERE key=?", (req["key"],)); c.commit()
            return {"status":"ok"}
        c.close()
        return {"status":"error","message":f"Unknown: {a}"}
    except Exception as e:
        return {"status":"error","message":str(e)}

init()
s = socket.socket(); s.setsockopt(1,2,1); s.bind((HOST,PORT)); s.listen(5)
while True:
    try:
        c,a = s.accept(); d = c.recv(65536)
        if d: c.sendall(json.dumps(handle(d.decode())).encode())
        c.close()
    except: pass