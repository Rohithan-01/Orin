"""Orin CLI main entry point."""

from __future__ import annotations

import typer
from rich.table import Table

from orin import __version__
from orin.cli.console import console, print_banner
from orin.cli.doctor import run_doctor
from orin.config.settings import (
    get_config,
    get_config_path,
    save_config,
)
from orin.voice.tts import (
    FEMALE_VOICE_PRIORITY,
    MALE_KEYWORDS,
    PIPER_FEMALE_VOICES,
    download_piper_voice,
    get_piper_voices_dir,
    get_tts_player,
)

app = typer.Typer(
    name="orin",
    help="Orin: Lightweight Local-First Voice Assistant for Windows",
    add_completion=False,
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    text: bool = typer.Option(
        False,
        "--text",
        "-t",
        help="Run Orin in text mode without voice reply.",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Display Orin version and exit.",
    ),
) -> None:
    """Orin main entry point. Runs assistant when no subcommand is provided."""
    if version:
        console.print(f"[bold cyan]Orin[/bold cyan] version [bold green]{__version__}[/bold green]")
        raise typer.Exit()

    # If a subcommand (e.g. doctor, status, voice) was invoked, don't run the chat loop here
    if ctx.invoked_subcommand is not None:
        return

    config = get_config()

    from orin.core.agent import OrinAgent

    agent = OrinAgent(config=config, speak_by_default=not text)
    if text:
        agent.run_text_chat_loop(speak=False)
    else:
        agent.run_voice_conversation_loop()


@app.command()
def listen(
    mode: str = typer.Argument(
        "status",
        help="Listening mode: 'on' (enables 'Hey Orin' VAD), 'off' (F9 push-to-talk only), or 'status'.",
    ),
) -> None:
    """Control background voice activation ('orin listen on' / 'orin listen off')."""
    config = get_config()
    cmd = mode.lower().strip()

    if cmd == "on":
        config.voice.wake_word_enabled = True
        save_config(config)
        console.print("[bold green][OK] Continuous 'Hey Orin' listening enabled (low-CPU VAD active).[/bold green]")
        console.print("[dim]Orin will listen for 'Hey Orin' or F9 push-to-talk.[/dim]")
    elif cmd == "off":
        config.voice.wake_word_enabled = False
        save_config(config)
        console.print("[bold yellow][OK] Continuous listening disabled. Push-to-talk (F9) active.[/bold yellow]")
    else:
        status_str = "ENABLED ('Hey Orin' + F9)" if config.voice.wake_word_enabled else "DISABLED (F9 Push-to-Talk only)"
        console.print(f"Current background listening status: [bold cyan]{status_str}[/bold cyan]")


@app.command()
def doctor() -> None:
    """Run comprehensive system diagnostics (Ollama, model, mic, speakers, audio, permissions)."""
    print_banner("System Diagnostics & Health Check")
    config = get_config()
    success = run_doctor(config)
    if not success:
        raise typer.Exit(code=1)


@app.command()
def status() -> None:
    """Show current Orin configuration, system status, and allowlisted folders."""
    print_banner("System Status")
    config = get_config()

    from orin.cli.console import format_status_bar
    from orin.cli.doctor import check_connectivity

    conn_res = check_connectivity()
    is_online = conn_res.status == "PASS"

    status_bar = format_status_bar(
        online=is_online,
        mode="VOICE" if not config.voice.muted else "TEXT (Muted)",
        listening=False,
        model=config.llm.model,
        user_name=config.general.user_name,
    )
    console.print(status_bar)
    console.print()

    table = Table(title="Configuration Details", border_style="blue", show_header=True)
    table.add_column("Setting", style="bold cyan", width=25)
    table.add_column("Value", style="white")

    table.add_row("Config File", str(get_config_path()))
    table.add_row("User Name", config.general.user_name)
    table.add_row("Ollama Host", config.llm.host)
    table.add_row("LLM Model", config.llm.model)
    table.add_row("TTS Engine", config.voice.engine)
    table.add_row("Voice ID", config.voice.voice_id or "Auto Female (Zira/Heera)")
    table.add_row("Speech Rate", f"{config.voice.rate} wpm")
    table.add_row("Voice Muted", str(config.voice.muted))
    table.add_row("Push-to-Talk Hotkey", f"{config.voice.hotkey} (or ENTER in terminal)")
    table.add_row("STT Model", f"{config.voice.stt_model} ({config.voice.stt_compute})")

    folders = "\n".join(config.security.allowlisted_folders) if config.security.allowlisted_folders else "None"
    table.add_row("Allowlisted Folders", folders)

    console.print(table)


@app.command()
def setup() -> None:
    """Interactive setup wizard to configure user preferences and allowlisted folders."""
    print_banner("First-Run Setup Wizard")
    config = get_config()

    console.print("[bold]Welcome to Orin setup![/bold] Let's customize your local assistant.\n")

    name = typer.prompt("Your name", default=config.general.user_name)
    config.general.user_name = name

    model = typer.prompt("Ollama LLM model", default=config.llm.model)
    config.llm.model = model

    rate = typer.prompt("Speech rate (words per minute)", default=str(config.voice.rate))
    try:
        config.voice.rate = int(rate)
    except ValueError:
        pass

    hotkey = typer.prompt("Push-to-talk hotkey (e.g. F9, F8, Ctrl+Space)", default=config.voice.hotkey)
    config.voice.hotkey = hotkey

    config.general.first_run = False
    save_config(config)

    console.print("\n[bold green][OK] Configuration saved to:[/bold green]", str(get_config_path()))
    console.print("[dim]You can re-run 'orin setup' or edit config.toml at any time.[/dim]\n")


@app.command()
def say(
    text: str = typer.Argument(..., help="The sentence or text for Orin to speak."),
) -> None:
    """Speak a sentence out loud using the configured female voice."""
    config = get_config()
    console.print(f"[bold cyan]Orin speaking:[/bold cyan] {text}")
    try:
        import pyttsx3

        engine = pyttsx3.init()
        engine.setProperty("rate", config.voice.rate or 170)
        engine.setProperty("volume", config.voice.volume or 1.0)
        if config.voice.voice_id:
            engine.setProperty("voice", config.voice.voice_id)
        engine.say(text)
        engine.runAndWait()
        console.print("[green][OK] Completed speech synthesis.[/green]")
    except Exception as e:
        console.print(f"[bold red]Speech error:[/bold red] {e}")


@app.command()
def voice(
    sample: int = typer.Option(
        -1,
        "--sample",
        "-s",
        help="Voice index to play a sample for.",
    ),
    select: int = typer.Option(
        -1,
        "--select",
        help="Voice index to select and save as default.",
    ),
    rate: int = typer.Option(
        0,
        "--rate",
        "-r",
        help="Set speech rate in words per minute (e.g. 170).",
    ),
    hotkey: str = typer.Option(
        "",
        "--hotkey",
        "-k",
        help="Set push-to-talk hotkey (e.g. 'F9', 'F8', 'Ctrl+Space').",
    ),
    download_piper: str = typer.Option(
        "",
        "--download-piper",
        "-d",
        help="Download Piper female voice: 'amy', 'hfc_female', or 'jenny'.",
    ),
) -> None:
    """List available voices, test female speech, and configure voice settings."""
    print_banner("Voice & Speech Settings")
    config = get_config()

    # Handle hotkey change
    if hotkey:
        config.voice.hotkey = hotkey.strip()
        save_config(config)
        console.print(f"[bold green][OK] Push-to-talk hotkey set to: {config.voice.hotkey}[/bold green]")
        console.print(f"[dim]You can now use '{config.voice.hotkey}' or press ENTER in terminal to speak.[/dim]")

    # Handle download piper voice request
    if download_piper:
        key = download_piper.lower().strip()
        if key in PIPER_FEMALE_VOICES:
            console.print(f"Downloading Piper neural voice '{key}' for offline use...")
            result = download_piper_voice(key)
            if result:
                console.print(f"[bold green][OK] Piper voice '{key}' downloaded to {result[0].parent}[/bold green]")
            else:
                console.print("[bold red][X] Download failed. Check internet connectivity.[/bold red]")
        else:
            options = ", ".join(PIPER_FEMALE_VOICES.keys())
            console.print(f"[bold yellow]Unknown Piper voice '{key}'. Options: {options}[/bold yellow]")
        return

    # Handle rate change
    if rate > 0:
        config.voice.rate = rate
        save_config(config)
        console.print(f"[bold green][OK] Speech rate set to {rate} words per minute.[/bold green]")

    try:
        import pyttsx3

        engine = pyttsx3.init()
        voices = engine.getProperty("voices") or []

        # If user passed --select
        if 0 <= select < len(voices):
            chosen = voices[select]
            config.voice.voice_id = chosen.id
            save_config(config)
            console.print(f"[bold green][OK] Active voice set to: {chosen.name}[/bold green]")

        # If user passed --sample
        if 0 <= sample < len(voices):
            sample_voice = voices[sample]
            console.print(f"[cyan]Playing sample for voice [{sample}] {sample_voice.name}...[/cyan]")
            engine.setProperty("voice", sample_voice.id)
            engine.setProperty("rate", config.voice.rate or 170)
            engine.say(f"Hi {config.general.user_name}, I am {sample_voice.name}. Ready to assist you.")
            engine.runAndWait()
            return

        table = Table(title="Installed Windows Voices (SAPI)", border_style="cyan")
        table.add_column("Idx", style="dim", width=4)
        table.add_column("Name", style="bold", width=32)
        table.add_column("Type", width=10)
        table.add_column("Status", width=12)

        active_id = config.voice.voice_id

        for idx, v in enumerate(voices):
            name_lower = v.name.lower()
            is_female = any(f in name_lower for f in FEMALE_VOICE_PRIORITY) or "female" in getattr(v, "gender", "").lower()
            is_male = any(m in name_lower for m in MALE_KEYWORDS)

            if is_female:
                vtype = "[bold magenta]Female[/bold magenta]"
            elif is_male:
                vtype = "[dim yellow]Male[/dim yellow]"
            else:
                vtype = "[dim]Standard[/dim]"

            is_active = (v.id == active_id) or (not active_id and is_female)
            status_text = "[bold green]Active (Default)[/bold green]" if is_active else "[dim]Available[/dim]"

            table.add_row(str(idx), v.name, vtype, status_text)

        console.print(table)

        # Piper voices section
        piper_dir = get_piper_voices_dir()
        console.print("\n[bold]Piper Neural Voices (High Quality Offline):[/bold]")
        for k, v in PIPER_FEMALE_VOICES.items():
            model_file = piper_dir / f"{v['name']}.onnx"
            status_str = "[green]Downloaded[/green]" if model_file.exists() else "[dim]Not downloaded (Run: orin voice -d " + k + ")[/dim]"
            console.print(f"  • [bold cyan]{k}[/bold cyan] ({v['name']}): {status_str}")

        console.print(f"\n[bold]Current Engine:[/bold] {config.voice.engine}")
        console.print(f"[bold]Current Rate:[/bold] {config.voice.rate} wpm (natural cadence)")
        console.print(f"[bold]Muted:[/bold] {config.voice.muted}")
        console.print(f"[bold]Push-to-Talk Hotkey:[/bold] {config.voice.hotkey}")
        console.print("\n[dim]Tips: Use 'orin voice --sample <idx>' to test a voice, or 'orin voice --select <idx>' to switch.[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error querying voice engine:[/bold red] {e}")


@app.command()
def index() -> None:
    """Trigger background indexing of allowlisted folders into SQLite FTS5."""
    print_banner("Full-Text File Indexer")
    config = get_config()
    from orin.tools.indexer import get_file_indexer

    indexer = get_file_indexer()
    folders = config.security.allowlisted_folders
    console.print(f"Indexing allowlisted folders ({len(folders)} configured)...")
    for f in folders:
        console.print(f"  • {f}")

    indexed, skipped = indexer.index_folders(folders)
    total = indexer.get_indexed_count()
    console.print(
        f"\n[bold green][OK] Indexing complete![/bold green] Indexed/Updated: [bold cyan]{indexed}[/bold cyan] | Unchanged: [dim]{skipped}[/dim] | Total in index: [bold green]{total}[/bold green]\n"
    )


@app.command()
def weather(
    location: str = typer.Argument(
        "",
        help="Location or city name (e.g. 'London', 'Tokyo'). Defaults to configured weather location.",
    ),
) -> None:
    """Fetch current weather report and spoken summary."""
    print_banner("Weather Forecast")
    from orin.net.weather import get_weather

    config = get_config()
    result = get_weather(location=location, config=config)
    if result["success"]:
        console.print(f"[bold cyan]Location:[/bold cyan] {result['location']}")
        console.print(f"[bold green]Condition:[/bold green] {result['condition'].capitalize()}")
        console.print(f"[bold]Temperature:[/bold] {result['temperature_c']}°C")
        console.print(f"[dim]Humidity: {result['humidity']}% | Wind: {result['wind_speed_kmh']} km/h[/dim]\n")
        console.print(f"[italic]{result['spoken']}[/italic]")
    else:
        console.print(f"[yellow]{result['spoken']}[/yellow]")


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query or question for web lookup."),
) -> None:
    """Perform quick web lookup and summary via DuckDuckGo / Wikipedia."""
    print_banner("Online Search")
    from orin.net.search import search_web

    result = search_web(query=query)
    if result["success"]:
        console.print(f"[bold cyan]Source:[/bold cyan] {result.get('source', 'Web')}")
        console.print(f"[bold green]Title:[/bold green] {result.get('title', query)}\n")
        console.print(result["snippet"])
    else:
        console.print(f"[yellow]{result['spoken']}[/yellow]")



@app.command(name="install-autostart")
def install_autostart_cmd() -> None:
    """Register Orin to run at Windows startup."""
    print_banner("Windows Startup Configuration")
    from orin.cli.autostart import install_autostart

    success, msg = install_autostart()
    if success:
        console.print(f"[bold green][OK] {msg}[/bold green]")
    else:
        console.print(f"[bold red][X] {msg}[/bold red]")


@app.command(name="remove-autostart")
def remove_autostart_cmd() -> None:
    """Remove Orin from Windows startup."""
    print_banner("Windows Startup Configuration")
    from orin.cli.autostart import remove_autostart

    success, msg = remove_autostart()
    if success:
        console.print(f"[bold green][OK] {msg}[/bold green]")
    else:
        console.print(f"[bold red][X] {msg}[/bold red]")


@app.command()
def audit(
    limit: int = typer.Option(20, "--limit", "-l", help="Number of recent audit entries to display."),
) -> None:
    """Display recent security audit log records."""
    print_banner("Security Audit Trail")
    from orin.security.audit import get_audit_logger

    audit_logger = get_audit_logger()
    entries = audit_logger.get_recent_logs(limit=limit)

    if not entries:
        console.print("[dim]No actions recorded in audit log yet.[/dim]")
        return

    table = Table(title="Recent Assistant Actions", border_style="cyan", show_lines=True)
    table.add_column("ID", style="dim", width=5)
    table.add_column("Timestamp", style="white", width=20)
    table.add_column("Action", style="bold cyan", width=20)
    table.add_column("Risk", width=10)
    table.add_column("Confirmed", width=11, justify="center")
    table.add_column("Details", style="italic")

    for e in entries:
        risk = e["risk_level"]
        if risk == "HIGH":
            risk_style = "[bold red]HIGH[/bold red]"
        elif risk == "MEDIUM":
            risk_style = "[yellow]MEDIUM[/yellow]"
        else:
            risk_style = "[green]LOW[/green]"

        conf_str = "[green]Yes[/green]" if e["confirmed"] else "[red]No[/red]"
        table.add_row(str(e["id"]), e["timestamp"], e["action"], risk_style, conf_str, e["details"])

    console.print(table)


@app.command()
def stop() -> None:
    """Emergency kill switch: stops active speaking and terminates running Orin processes."""
    get_tts_player().interrupt()
    console.print("[bold red]Orin emergency stop triggered: speech halted.[/bold red]")


@app.command(name="help")
def help_command() -> None:
    """List and explain all available Orin commands and voice capabilities."""
    print_banner("Orin Commands & Capabilities")

    table = Table(title="Available CLI Commands", border_style="cyan", show_lines=True)
    table.add_column("Command", style="bold cyan", width=25)
    table.add_column("Description", style="white")

    table.add_row("orin", "Start hands-free voice assistant (F9/ENTER to activate, continuous chat)")
    table.add_row("orin --text", "Interactive text chat loop in terminal without voice output")
    table.add_row("orin help", "Display this detailed help guide of commands and capabilities")
    table.add_row("orin doctor", "Run comprehensive health checks (Ollama, mic, speakers, TTS)")
    table.add_row("orin status", "Show configuration, active voice, hotkey, and allowlist")
    table.add_row("orin setup", "Run the interactive configuration wizard")
    table.add_row("orin say '<text>'", "Speak a sentence out loud using Microsoft Zira")
    table.add_row("orin voice", "Configure speech rate, list voices, and select default voice")
    table.add_row("orin voice --hotkey <key>", "Change push-to-talk hotkey (e.g. F9, F8, Ctrl+Space)")
    table.add_row("orin index", "Crawl allowlisted folders and index files into SQLite FTS5")
    table.add_row("orin audit", "View security audit trail of all executed tool actions")
    table.add_row("orin install-autostart", "Configure Orin to start automatically with Windows")
    table.add_row("orin remove-autostart", "Remove Orin from Windows startup")
    table.add_row("orin stop", "Emergency kill switch: halts active speech synthesis")

    console.print(table)

    console.print("\n[bold]Voice Commands (in Voice or Text mode):[/bold]")
    console.print("  • [cyan]What can you do?[/cyan] -> Lists voice capabilities out loud")
    console.print("  • [cyan]What is my battery level?[/cyan] -> Reports battery percentage and power state")
    console.print("  • [cyan]Check system status[/cyan] -> Reports CPU and RAM usage")
    console.print("  • [cyan]Mute audio / Set volume to 75[/cyan] -> Adjusts system volume")
    console.print("  • [cyan]Open Notepad / Launch Calculator[/cyan] -> Starts approved applications")
    console.print("  • [cyan]Take a note: <content>[/cyan] -> Saves a note to local database")
    console.print("  • [cyan]Show my notes[/cyan] -> Lists recent notes")
    console.print("  • [cyan]Remind me to <task>[/cyan] -> Creates a scheduled reminder")
    console.print("  • [cyan]Search files for <keyword>[/cyan] -> Fast FTS5 search in allowlisted folders")
    console.print("  • [cyan]That's all / Goodbye[/cyan] -> Exits continuous voice conversation loop\n")


if __name__ == "__main__":
    app()
