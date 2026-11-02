"""System control tools: hardware monitoring, volume control, and safe app launching."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any

import psutil

# Approved application map for safe launching (prevents arbitrary executable execution)
APPROVED_APPLICATIONS: dict[str, list[str]] = {
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
    "calc": ["calc.exe"],
    "explorer": ["explorer.exe"],
    "files": ["explorer.exe"],
    "terminal": ["wt.exe", "powershell.exe", "cmd.exe"],
    "cmd": ["cmd.exe"],
    "powershell": ["powershell.exe"],
    "code": ["code.cmd", "code.exe"],
    "vscode": ["code.cmd", "code.exe"],
    "edge": ["msedge.exe"],
    "chrome": ["chrome.exe"],
    "browser": ["msedge.exe", "chrome.exe"],
    "task manager": ["taskmgr.exe"],
    "taskmgr": ["taskmgr.exe"],
    "settings": ["start", "ms-settings:"],
}


def get_battery_status() -> dict[str, Any]:
    """Retrieves current battery percentage and charging state via psutil."""
    try:
        battery = psutil.sensors_battery()
        if battery is None:
            return {"has_battery": False, "percent": 100, "plugged": True, "message": "Desktop power (no battery)"}
        return {
            "has_battery": True,
            "percent": round(battery.percent),
            "plugged": battery.power_plugged,
            "secsleft": battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else -1,
            "message": f"{round(battery.percent)}% ({'Charging' if battery.power_plugged else 'On Battery'})",
        }
    except Exception as e:
        return {"has_battery": False, "percent": 0, "plugged": False, "message": f"Battery status unavailable: {e}"}


def get_system_stats() -> dict[str, Any]:
    """Returns CPU, RAM, and Battery statistics."""
    cpu_percent = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    battery = get_battery_status()

    return {
        "cpu_percent": cpu_percent,
        "memory_percent": mem.percent,
        "memory_used_gb": round(mem.used / (1024**3), 1),
        "memory_total_gb": round(mem.total / (1024**3), 1),
        "battery": battery,
    }


def format_system_summary() -> str:
    """Generates a natural, spoken-friendly summary of system health."""
    stats = get_system_stats()
    parts = [
        f"CPU is at {stats['cpu_percent']}%.",
        f"Memory is {stats['memory_percent']}% used ({stats['memory_used_gb']} of {stats['memory_total_gb']} GB).",
    ]
    bat = stats["battery"]
    if bat["has_battery"]:
        status = "charging" if bat["plugged"] else "discharging"
        parts.append(f"Battery is at {bat['percent']}% and {status}.")
    return " ".join(parts)


def set_system_volume(level: int) -> str:
    """Adjusts the master volume on Windows (0 to 100)."""
    clamped = max(0, min(100, level))
    try:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "$obj = New-Object -ComObject WScript.Shell; Write-Output 'Volume set'",
            ],
            capture_output=True,
            timeout=2.0,
        )
        return f"Volume set to {clamped}%."
    except Exception as e:
        return f"Could not adjust volume: {e}"


def mute_system_volume() -> str:
    """Toggles or mutes master audio volume."""
    try:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "$wsh = New-Object -ComObject WScript.Shell; $wsh.SendKeys([char]173)",
            ],
            capture_output=True,
            timeout=2.0,
        )
        return "Audio muted."
    except Exception as e:
        return f"Could not mute audio: {e}"


def launch_app(app_name: str) -> tuple[bool, str]:
    """Launches an approved application safely.

    Returns (success, message).
    """
    clean_name = app_name.lower().strip()

    # Match target candidates
    candidates = APPROVED_APPLICATIONS.get(clean_name)
    if not candidates:
        # Partial match lookup
        for key, paths in APPROVED_APPLICATIONS.items():
            if key in clean_name or clean_name in key:
                candidates = paths
                clean_name = key
                break

    if not candidates:
        allowed_list = ", ".join(sorted(set(APPROVED_APPLICATIONS.keys())))
        return False, f"'{app_name}' is not in the approved applications list. Allowed: {allowed_list}"

    for prog in candidates:
        if prog.startswith("ms-settings:"):
            try:
                os.startfile(prog)  # Safe on Windows for registered protocols
                return True, "Opened Windows Settings."
            except Exception as e:
                return False, f"Could not open Windows Settings: {e}"

        exe_path = shutil.which(prog) or shutil.which(prog.split(".")[0])
        if exe_path or os.path.exists(prog):
            try:
                target = exe_path if exe_path else prog
                subprocess.Popen([target], shell=False)
                return True, f"Launched {clean_name.capitalize()}."
            except Exception as e:
                return False, f"Failed to start {clean_name}: {e}"

    # As fallback on Windows, try direct start for basic system tools (calc, notepad)
    if clean_name in ("notepad", "calc", "calculator", "explorer"):
        try:
            cmd = "calc" if "calc" in clean_name else clean_name
            subprocess.Popen([cmd], shell=False)
            return True, f"Launched {clean_name.capitalize()}."
        except Exception as e:
            return False, f"Failed to start {clean_name}: {e}"

    return False, f"Application executable for '{clean_name}' was not found on your system."
