"""Console formatting, banners, and real-time status bar rendering for Orin."""

from __future__ import annotations

import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Force UTF-8 stream reconfiguration on Windows to prevent cp1252 charmap encoding errors
if sys.platform == "win32":
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

console = Console()
err_console = Console(stderr=True)

ORIN_BANNER = """
   ___  ___  _____ _  __
  / _ \\/ _ \\|_   _| \\| |
 | (_) |   / _| |_| .` |
  \\___/|_|_\\|_____|_|\\_|
"""


def print_banner(subtitle: str = "Lightweight Local-First Voice Assistant") -> None:
    """Print the Orin banner in the terminal."""
    banner_text = Text(ORIN_BANNER, style="bold cyan")
    banner_text.append(f"\n  {subtitle}\n", style="dim italic")
    console.print(Panel(banner_text, border_style="cyan", expand=False))


def format_status_bar(
    online: bool,
    mode: str,
    listening: bool,
    model: str,
    user_name: str = "User",
) -> Panel:
    """Renders the single-line status bar for the assistant interface."""
    status_text = Text()

    if online:
        status_text.append(" [ONLINE] ", style="bold black on green")
    else:
        status_text.append(" [OFFLINE] ", style="bold white on red")

    status_text.append(" ")

    if mode.lower() == "voice":
        status_text.append("[VOICE] ", style="bold magenta")
    else:
        status_text.append("[TEXT] ", style="bold yellow")

    if listening:
        status_text.append("(*) LISTENING ", style="bold green")
    else:
        status_text.append("( ) IDLE ", style="dim")

    status_text.append(f"| Model: {model} ", style="bold cyan")
    status_text.append(f"| User: {user_name}", style="italic dim")

    return Panel(status_text, border_style="blue", expand=False)


def format_voice_state_bar(
    state: str,
    online: bool = True,
    model: str = "llama3.2:3b",
    user_name: str = "User",
    hotkey: str = "F9",
) -> Panel:
    """Renders the exact 4-state voice status line: IDLE, LISTENING, THINKING, SPEAKING."""
    bar = Text()

    # Online indicator
    if online:
        bar.append(" [ONLINE] ", style="bold black on green")
    else:
        bar.append(" [OFFLINE] ", style="bold white on red")
    bar.append(" ")

    state_upper = state.upper()
    if state_upper == "IDLE":
        bar.append(" [IDLE] ", style="bold black on white")
        bar.append(f" Ready • Press {hotkey} or ENTER in terminal to speak • 'orin listen on' for hands-free ", style="dim")
    elif state_upper == "LISTENING":
        bar.append(" [LISTENING] ", style="bold black on green")
        bar.append(f" Listening to your voice... (Release {hotkey} or pause to send) ", style="bold green")
    elif state_upper == "THINKING":
        bar.append(" [THINKING] ", style="bold black on yellow")
        bar.append(" Transcribing & processing query... ", style="bold yellow")
    elif state_upper == "SPEAKING":
        bar.append(" [SPEAKING] ", style="bold white on magenta")
        bar.append(f" Speaking out loud • Press {hotkey} or say 'stop' to interrupt ", style="bold magenta")
    else:
        bar.append(f" [{state_upper}] ", style="bold cyan")

    bar.append(f"| {model} ", style="cyan dim")
    return Panel(bar, border_style="cyan", expand=False)


def create_doctor_table() -> Table:
    """Creates a Rich table for displaying diagnostic checks."""
    table = Table(
        title="Orin System Diagnostics (orin doctor)",
        border_style="bright_blue",
        header_style="bold cyan",
        show_lines=True,
    )
    table.add_column("Component", style="bold", width=22)
    table.add_column("Status", width=10, justify="center")
    table.add_column("Details", style="white")
    table.add_column("Remedy / Fix", style="yellow")
    return table
