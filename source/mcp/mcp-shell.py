#!/usr/bin/env python3
"""George's MCP Shell Service — real shell execution via TCP socket"""
import socket, json, subprocess, sys, os

HOST = '127.0.0.1'
PORT = 9104

def handle_request(data):
    """Process a shell exec request"""
    try:
        req = json.loads(data)
        if req.get("action") == "exec":
            cmd = req.get("cmd", "")
            timeout = min(req.get("timeout", 10), 30)
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            return {"status": "ok", "stdout": result.stdout[:5000], "stderr": result.stderr[:1000], "code": result.returncode}
        elif req.get("action") == "ping":
            return {"status": "pong"}
        else:
            return {"status": "error", "message": f"Unknown action: {req.get('action')}"}
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "Command timed out"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def serve():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(5)
    
    while True:
        try:
            conn, addr = s.accept()
            data = conn.recv(65536)
            if data:
                response = handle_request(data.decode())
                conn.sendall(json.dumps(response).encode())
            conn.close()
        except Exception:
            pass

if __name__ == "__main__":
    serve()