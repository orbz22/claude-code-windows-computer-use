"""State shared by the MCP server and the Stop hook (turn_end.py)."""

from __future__ import annotations

import json
import os
import subprocess
import time

import psutil

STATE_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "claude-win-computer-use")
LOCK_PATH = os.path.join(STATE_DIR, "computer-use.lock")
os.makedirs(STATE_DIR, exist_ok=True)

CREATE_NO_WINDOW = 0x08000000
CLAUDE_NAMES = ("claude.exe", "claude", "node.exe", "bun.exe")


def state_path(pid: int) -> str:
    return os.path.join(STATE_DIR, f"state-{pid}.json")


def read_json(path: str) -> dict | None:
    for _ in range(5):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except (json.JSONDecodeError, PermissionError):
            time.sleep(0.02)
    return None


def write_json(path: str, data: dict) -> None:
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    for _ in range(10):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.02)
    os.replace(tmp, path)


def process_alive(pid: int, create_time: float | None = None) -> bool:
    try:
        p = psutil.Process(pid)
        if create_time is not None and abs(p.create_time() - create_time) > 1:
            return False
        return p.is_running() and p.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def claude_ancestor(pid: int | None = None) -> int | None:
    """PID of the Claude Code process this process runs under."""
    try:
        p = psutil.Process(pid or os.getpid())
        for parent in p.parents()[:10]:
            name = parent.name().lower()
            if name in CLAUDE_NAMES or name.startswith("claude"):
                return parent.pid
    except psutil.Error:
        pass
    return None


def notify(text: str, title: str = "Claude") -> None:
    """Fire-and-forget Windows notification (tray balloon, shown as a toast)."""
    script = (
        "Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
        "$n=New-Object System.Windows.Forms.NotifyIcon;"
        "$n.Icon=[System.Drawing.SystemIcons]::Information;"
        "$n.Visible=$true;"
        "$n.ShowBalloonTip(5000,$env:CU_TITLE,$env:CU_TEXT,'Info');"
        "Start-Sleep -Seconds 6;$n.Dispose()"
    )
    env = {**os.environ, "CU_TITLE": title, "CU_TEXT": text}
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", script],
            env=env, creationflags=CREATE_NO_WINDOW,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass


def restore_windows(hwnds: list[int]) -> None:
    import winapi  # local import: keeps the hook light when nothing is hidden

    for h in reversed(hwnds):
        try:
            winapi.unminimize(h)
        except Exception:
            pass
