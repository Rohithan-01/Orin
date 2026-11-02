"""Windows autostart registration using HKCU CurrentVersion\\Run registry key."""

from __future__ import annotations

import shutil
import sys

REG_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "OrinAssistant"


def get_orin_launch_command() -> str:
    """Computes the appropriate command line string to launch Orin at startup."""
    orin_exe = shutil.which("orin")
    if orin_exe:
        return f'"{orin_exe}"'

    python_exe = sys.executable
    return f'"{python_exe}" -m orin.cli.main'


def install_autostart() -> tuple[bool, str]:
    """Registers Orin to launch automatically on Windows login."""
    if sys.platform != "win32":
        return False, "Autostart registration is only supported on Windows."

    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REG_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE,
        )
        cmd = get_orin_launch_command()
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        return True, f"Orin registered for Windows startup: {cmd}"
    except Exception as e:
        return False, f"Failed to register Windows startup key: {e}"


def remove_autostart() -> tuple[bool, str]:
    """Removes Orin from Windows startup."""
    if sys.platform != "win32":
        return False, "Autostart removal is only supported on Windows."

    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REG_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE,
        )
        try:
            winreg.DeleteValue(key, APP_NAME)
        except FileNotFoundError:
            winreg.CloseKey(key)
            return True, "Orin was not registered in Windows startup."

        winreg.CloseKey(key)
        return True, "Orin removed from Windows startup."
    except Exception as e:
        return False, f"Failed to remove Windows startup key: {e}"


def is_autostart_installed() -> bool:
    """Checks whether Orin is currently registered in Windows startup."""
    if sys.platform != "win32":
        return False

    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REG_KEY_PATH,
            0,
            winreg.KEY_READ,
        )
        try:
            val, _ = winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            return bool(val)
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception:
        return False
