"""System diagnostics and health checks for Orin."""

from __future__ import annotations

import socket
import sys
from dataclasses import dataclass

import httpx

from orin.cli.console import console, create_doctor_table
from orin.config.settings import OrinConfig, get_config, get_config_dir


@dataclass
class DiagnosticResult:
    component: str
    status: str  # "PASS", "WARN", "FAIL"
    details: str
    remedy: str = ""


def check_python_version() -> DiagnosticResult:
    """Verifies that Python 3.13+ is in use."""
    version_info = sys.version_info
    ver_str = f"{version_info.major}.{version_info.minor}.{version_info.micro}"
    if version_info.major == 3 and version_info.minor == 13:
        return DiagnosticResult(
            component="Python Runtime",
            status="PASS",
            details=f"Python {ver_str} (Target: Python 3.13)",
            remedy="None needed",
        )
    elif version_info.major == 3 and version_info.minor > 13:
        return DiagnosticResult(
            component="Python Runtime",
            status="WARN",
            details=f"Python {ver_str} (>= 3.13, project standard is 3.13)",
            remedy="Works, but 3.13 is the primary supported version",
        )
    else:
        return DiagnosticResult(
            component="Python Runtime",
            status="FAIL",
            details=f"Python {ver_str} is unsupported (< 3.13)",
            remedy="Install Python 3.13 and run: py -3.13 -m venv .venv",
        )


def check_ollama_server(config: OrinConfig) -> tuple[DiagnosticResult, bool]:
    """Checks if the Ollama daemon is reachable at localhost:11434."""
    url = f"{config.llm.host}/api/version"
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                version = data.get("version", "unknown")
                return (
                    DiagnosticResult(
                        component="Ollama Service",
                        status="PASS",
                        details=f"Running at {config.llm.host} (v{version})",
                        remedy="None needed",
                    ),
                    True,
                )
            else:
                return (
                    DiagnosticResult(
                        component="Ollama Service",
                        status="FAIL",
                        details=f"Server returned HTTP {resp.status_code}",
                        remedy="Restart Ollama: 'ollama serve' or check host config",
                    ),
                    False,
                )
    except Exception as e:
        return (
            DiagnosticResult(
                component="Ollama Service",
                status="FAIL",
                details=f"Cannot connect to {config.llm.host} ({type(e).__name__})",
                remedy="Start Ollama application or run 'ollama serve' in a terminal",
            ),
            False,
        )


def check_ollama_model(config: OrinConfig, server_ok: bool) -> DiagnosticResult:
    """Checks if the configured model (default llama3.2:3b) is pulled in Ollama."""
    if not server_ok:
        return DiagnosticResult(
            component="Ollama Model",
            status="FAIL",
            details="Skipped because Ollama server is unreachable",
            remedy="Start Ollama first, then check models",
        )

    url = f"{config.llm.host}/api/tags"
    target_model = config.llm.model
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                # Match full or prefix (e.g. 'llama3.2:3b' or 'llama3.2:latest')
                found = any(
                    target_model == m or target_model == m.split(":")[0] or m.startswith(target_model)
                    for m in models
                )
                if found:
                    return DiagnosticResult(
                        component="Ollama Model",
                        status="PASS",
                        details=f"Model '{target_model}' is installed and ready",
                        remedy="None needed",
                    )
                else:
                    installed_list = ", ".join(models) if models else "none"
                    return DiagnosticResult(
                        component="Ollama Model",
                        status="FAIL",
                        details=f"'{target_model}' not found (Installed: {installed_list})",
                        remedy=f"Run: ollama pull {target_model}",
                    )
            return DiagnosticResult(
                component="Ollama Model",
                status="FAIL",
                details=f"Failed to query models (HTTP {resp.status_code})",
                remedy="Check Ollama service status",
            )
    except Exception as e:
        return DiagnosticResult(
            component="Ollama Model",
            status="FAIL",
            details=f"Error checking models: {e}",
            remedy=f"Run: ollama pull {target_model}",
        )


def check_audio_devices() -> tuple[DiagnosticResult, DiagnosticResult]:
    """Queries input (microphone) and output (speaker) devices via sounddevice."""
    try:
        import sounddevice as sd

        # Input check
        try:
            in_dev = sd.query_devices(kind="input")
            name = in_dev.get("name", "Unknown Microphone")
            channels = in_dev.get("max_input_channels", 0)
            in_result = DiagnosticResult(
                component="Microphone (Audio In)",
                status="PASS",
                details=f"{name} ({channels} ch)",
                remedy="None needed",
            )
        except Exception as e:
            in_result = DiagnosticResult(
                component="Microphone (Audio In)",
                status="WARN",
                details=f"No default input device found ({e})",
                remedy="Connect a microphone or enable it in Windows Sound Settings",
            )

        # Output check
        try:
            out_dev = sd.query_devices(kind="output")
            name = out_dev.get("name", "Unknown Speaker")
            channels = out_dev.get("max_output_channels", 0)
            out_result = DiagnosticResult(
                component="Speakers (Audio Out)",
                status="PASS",
                details=f"{name} ({channels} ch)",
                remedy="None needed",
            )
        except Exception as e:
            out_result = DiagnosticResult(
                component="Speakers (Audio Out)",
                status="FAIL",
                details=f"No default audio output found ({e})",
                remedy="Connect speakers or headphones",
            )

        return in_result, out_result

    except ImportError:
        res = DiagnosticResult(
            component="Audio System",
            status="FAIL",
            details="sounddevice package not installed",
            remedy="Run: pip install sounddevice",
        )
        return res, res
    except Exception as e:
        res = DiagnosticResult(
            component="Audio System",
            status="FAIL",
            details=f"Audio subsystem error: {e}",
            remedy="Check Windows Audio service and sound drivers",
        )
        return res, res


def check_tts_engine() -> DiagnosticResult:
    """Verifies pyttsx3 Windows SAPI text-to-speech initialization."""
    try:
        import pyttsx3

        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        voice_count = len(voices) if voices else 0
        default_voice = voices[0].name if voices else "Unknown"
        return DiagnosticResult(
            component="TTS Engine (pyttsx3)",
            status="PASS",
            details=f"{voice_count} voice(s) found (Default: {default_voice})",
            remedy="None needed",
        )
    except ImportError:
        return DiagnosticResult(
            component="TTS Engine (pyttsx3)",
            status="WARN",
            details="pyttsx3 not installed or pywin32 missing",
            remedy="Run: pip install pyttsx3",
        )
    except Exception as e:
        return DiagnosticResult(
            component="TTS Engine (pyttsx3)",
            status="WARN",
            details=f"pyttsx3 initialization notice: {e}",
            remedy="Check Windows SAPI5 voices in Speech Settings",
        )


def check_storage_and_permissions() -> DiagnosticResult:
    """Checks read/write permissions for ~/.orin and verifies disk space."""
    import psutil

    config_dir = get_config_dir()
    try:
        # Test write and read
        test_file = config_dir / ".doctor_test.tmp"
        test_file.write_text("orin_write_test", encoding="utf-8")
        read_back = test_file.read_text(encoding="utf-8")
        test_file.unlink(missing_ok=True)

        if read_back != "orin_write_test":
            return DiagnosticResult(
                component="Storage & Access",
                status="FAIL",
                details=f"Write test mismatch at {config_dir}",
                remedy=f"Check permissions for directory: {config_dir}",
            )

        disk_usage = psutil.disk_usage(str(config_dir))
        free_gb = disk_usage.free / (1024**3)
        if free_gb < 1.0:
            return DiagnosticResult(
                component="Storage & Access",
                status="WARN",
                details=f"Writable at {config_dir}, but only {free_gb:.1f} GB disk space free",
                remedy="Free up disk space on system drive",
            )

        return DiagnosticResult(
            component="Storage & Access",
            status="PASS",
            details=f"Writable ({config_dir}), {free_gb:.1f} GB free",
            remedy="None needed",
        )
    except Exception as e:
        return DiagnosticResult(
            component="Storage & Access",
            status="FAIL",
            details=f"Cannot write to {config_dir}: {e}",
            remedy=f"Grant write permissions to user for {config_dir}",
        )


def check_connectivity() -> DiagnosticResult:
    """Checks internet connectivity (informational; offline is supported)."""
    # Quick probe to a public DNS port 53 with 1.5s timeout
    try:
        socket.setdefaulttimeout(1.5)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("1.1.1.1", 53))
        s.close()
        return DiagnosticResult(
            component="Network Connectivity",
            status="PASS",
            details="ONLINE (Internet accessible for search/weather)",
            remedy="None needed",
        )
    except Exception:
        return DiagnosticResult(
            component="Network Connectivity",
            status="WARN",
            details="OFFLINE (Core assistant features remain 100% operational)",
            remedy="Connect to Wi-Fi/Ethernet when web search or weather is desired",
        )


def run_doctor(config: OrinConfig | None = None) -> bool:
    """Runs all system diagnostic checks, prints a Rich table, and returns overall health status."""
    if config is None:
        config = get_config()

    console.print("\n[bold cyan]Running Orin System Diagnostics...[/bold cyan]\n")

    results: list[DiagnosticResult] = []

    # 1. Python version
    results.append(check_python_version())

    # 2. Ollama server & model
    ollama_server_res, server_ok = check_ollama_server(config)
    results.append(ollama_server_res)
    results.append(check_ollama_model(config, server_ok))

    # 3. Audio in & out
    mic_res, spk_res = check_audio_devices()
    results.append(mic_res)
    results.append(spk_res)

    # 4. TTS
    results.append(check_tts_engine())

    # 5. Storage
    results.append(check_storage_and_permissions())

    # 6. Network
    results.append(check_connectivity())

    # Build and print table
    table = create_doctor_table()
    all_passed = True
    any_warnings = False

    for r in results:
        if r.status == "PASS":
            status_text = "[bold green]PASS[/bold green]"
        elif r.status == "WARN":
            status_text = "[bold yellow]WARN[/bold yellow]"
            any_warnings = True
        else:
            status_text = "[bold red]FAIL[/bold red]"
            all_passed = False

        table.add_row(r.component, status_text, r.details, r.remedy)

    console.print(table)

    if all_passed and not any_warnings:
        console.print("\n[bold green][OK] All systems operational! Orin is ready to run.[/bold green]\n")
    elif all_passed and any_warnings:
        console.print(
            "\n[bold yellow][!] System is operational with minor warnings (see table above).[/bold yellow]\n"
        )
    else:
        console.print(
            "\n[bold red][X] Some checks failed. Please review the remedies above before starting voice mode.[/bold red]\n"
        )

    return all_passed
