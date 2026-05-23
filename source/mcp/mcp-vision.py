#!/usr/bin/env python3
"""George's MCP Vision Service — grab camera frames via RTSP"""
import socket, json, subprocess, os, base64, sys

HOST = '127.0.0.1'
PORT = 9103
CACHE_DIR = "/tmp/george_cam"
os.makedirs(CACHE_DIR, exist_ok=True)

CAMERAS = {
    "front-door": "rtsp://192.168.68.97:8554/front-door",
    "back-yard": "rtsp://192.168.68.97:8554/back-yard-cam",
    "kitchen": "rtsp://192.168.68.97:8554/kitchen-cam",
    "basement": "rtsp://192.168.68.97:8554/basement",
    "outside-front": "rtsp://192.168.68.97:8554/outside-front",
    "master-front": "rtsp://192.168.68.97:8554/master-front",
    "kids-room": "rtsp://192.168.68.97:8554/kids-room",
    "hillbilly-front": "rtsp://192.168.68.97:8554/hillbilly-front",
    "under-back-porch": "rtsp://192.168.68.97:8554/under-back-porch",
}

def grab_frame(camera_name):
    """Grab a single frame from an RTSP camera"""
    rtsp_url = CAMERAS.get(camera_name)
    if not rtsp_url:
        return {"status": "error", "message": f"Unknown camera: {camera_name}"}
    
    outpath = f"{CACHE_DIR}/{camera_name}.jpg"
    try:
        subprocess.run([
            "ffmpeg", "-y", "-rtsp_transport", "tcp",
            "-i", rtsp_url,
            "-frames:v", "1", "-s", "640x480",
            "-update", "1", outpath
        ], capture_output=True, text=True, timeout=15)
        
        if os.path.exists(outpath) and os.path.getsize(outpath) > 1000:
            with open(outpath, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            return {"status": "ok", "camera": camera_name, "path": outpath, "base64": b64[:200] + "...", "size": os.path.getsize(outpath)}
        return {"status": "error", "message": "Frame too small or missing"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def list_cameras():
    return {"status": "ok", "cameras": list(CAMERAS.keys()), "count": len(CAMERAS)}

def handle_request(data):
    try:
        req = json.loads(data)
        action = req.get("action", "ping")
        if action == "ping":
            return {"status": "pong", "service": "george-vision"}
        elif action == "list":
            return list_cameras()
        elif action == "grab":
            return grab_frame(req.get("camera", ""))
        elif action == "grab_all":
            results = {}
            for name in CAMERAS:
                results[name] = grab_frame(name)
            return {"status": "ok", "frames": results}
        else:
            return {"status": "error", "message": f"Unknown action: {action}"}
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