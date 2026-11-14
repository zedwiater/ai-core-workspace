# --- AI Core service label ---
# Label-Name: vision
# Label-Origin: ai-core-workspace build (Zak/Muse)
# Label-Version: 1
# Label-Does: camera frame grabs from local V4L2/USB cameras
# --- end label ---
#!/usr/bin/env python3
"""George's MCP Vision Service — grab camera frames via RTSP

Ring: atmosphere (outer ring — world-facing, takes the weather).
Runs the shared ring lifecycle: register -> serve -> report health.
"""
import base64
import os
import subprocess
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from core.ring_service import serve

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


def ping(req):
    return {"status": "pong", "service": "george-vision"}


def list_cams(req):
    return list_cameras()


def grab(req):
    return grab_frame(req.get("camera", ""))


def grab_all(req):
    results = {}
    for name in CAMERAS:
        results[name] = grab_frame(name)
    return {"status": "ok", "frames": results}


if __name__ == "__main__":
    serve("vision", "atmosphere", PORT,
          {"ping": ping, "list": list_cams, "grab": grab, "grab_all": grab_all})
