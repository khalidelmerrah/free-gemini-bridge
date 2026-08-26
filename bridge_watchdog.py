"""Watchdog for the Hermes Gemini bridge.

Checks http://127.0.0.1:8787/health; if the bridge is down AND the port is
free, (re)starts it detached. Logs to bridge-watchdog.log. Intended to run
from a scheduled task every few minutes.
"""
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HOME = Path(os.path.expanduser("~"))
REPO = HOME / "gemini-hermes"
PY = r"C:\Users\admindev\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
HOST, PORT = "127.0.0.1", 8787
LOG = REPO / "bridge-watchdog.log"


def log(msg: str):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")


def healthy() -> bool:
    try:
        with urllib.request.urlopen(f"http://{HOST}:{PORT}/health", timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def port_free() -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.close()
        return True
    except OSError:
        return False


def main():
    if healthy():
        return  # all good
    log("bridge unhealthy — investigating")
    if not port_free():
        log(f"port {PORT} is occupied by something else; not restarting")
        return
    log("port free — starting bridge")
    try:
        logfile = open(REPO / "bridge.log", "ab")
        subprocess.Popen(
            [PY, "-m", "uvicorn", "gemini_cli_bridge:app",
             "--host", HOST, "--port", str(PORT)],
            cwd=str(REPO),
            stdin=subprocess.DEVNULL,
            stdout=logfile,
            stderr=logfile,
            creationflags=subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NO_WINDOW
            | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
        log("bridge start attempted")
    except Exception as e:
        log(f"failed to start bridge: {e}")


if __name__ == "__main__":
    main()
