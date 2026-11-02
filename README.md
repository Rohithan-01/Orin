# Orin

Orin is a private, offline-first voice assistant for Windows. It runs locally on CPU, keeps voice processing on-device, and uses a rule-based command router to execute safe, user-approved actions without sending your data to external services.

The project combines:

- Local LLM inference through Ollama
- Local speech-to-text and wake-word/VAD support
- Local text-to-speech via Windows SAPI or Piper voices
- A privacy-first command router with allowlisted folders and audit logging
- A small set of local productivity actions like notes, reminders, file search, weather lookup, and system status checks

## Why Orin?

Orin is designed for people who want a personal assistant that is:

- Private: data stays local by default
- Offline-capable: works without cloud APIs
- Fast: optimized for local CPU execution
- Safe: restricts file access and records actions
- Lightweight: built for a desktop workflow rather than a cloud product

## Features

- Voice-first interaction with push-to-talk and optional wake-word listening
- Local LLM chat via Ollama with configurable model settings
- Offline TTS with Windows voice selection or downloaded Piper neural voices
- File indexing and local search inside allowlisted folders
- Notes and reminders stored locally
- Weather, web lookup, and system info actions
- Security controls including allowlisted folders, audit trail, and confirmation prompts for sensitive actions
- CLI-driven configuration and diagnostics

## Repository Layout

```text
Orin/
├── orin/
│   ├── cli/               # Typer CLI commands and setup flows
│   ├── config/            # TOML configuration and defaults
│   ├── core/              # Agent runtime, prompts, and command router
│   │   └── router/        # Intent classification and action dispatch
│   ├── llm/               # LLM integration and local model logic
│   ├── memory/            # Persistent memory-related helpers
│   ├── net/               # Network-related tools (weather, search)
│   ├── security/          # Audit logs and safety checks
│   ├── tools/             # Files, notes, reminders, system actions
│   ├── voice/             # Audio I/O, VAD, STT, and TTS
│   ├── __init__.py
│   └── ...
├── tests/                 # Pytest coverage for config, CLI, tools, voice, net, security
├── scratch/               # Experimental or throwaway work
├── .gitignore
├── pyproject.toml         # Package metadata and dependencies
├── README.md
└── LICENSE                # if added in your repo later
```

## Requirements

- Python 3.13+
- Windows 10/11
- Ollama installed and running locally
- Access to a local model such as `llama3.2:3b`
- Microphone and speaker available for voice interactions

Optional dependencies and runtime features:

- `pyttsx3` for native Windows speech synthesis
- Piper voices for higher-quality offline speech
- `faster-whisper`-style local STT flow via the project voice stack

## Installation

Clone the repository:

```bash
git clone https://github.com/Rohithan-01/Orin.git
cd Orin
```

Create and activate a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Install the package:

```bash
pip install -e .
```

If you want development tools as well:

```bash
pip install -e ".[dev]"
```

Ensure Ollama is running locally on the default host:

```bash
http://localhost:11434
```

## Quick Start

Run setup to configure the assistant:

```bash
orin setup
```

Check the system health:

```bash
orin doctor
```

View current status and configuration:

```bash
orin status
```

Launch the voice assistant:

```bash
orin
```

Run in text-only mode:

```bash
orin --text
```

Enable or disable wake-word background listening:

```bash
orin listen on
orin listen off
```

Display available commands:

```bash
orin help
```

## Common Commands

```bash
orin setup
orin doctor
orin status
orin listen on
orin listen off
orin say "Hello from Orin"
orin voice --sample 0
orin voice --rate 180
orin voice --download-piper amy
orin index
orin audit
orin stop
```

## Configuration

Orin stores configuration in:

```text
~/.orin/config.toml
```

You can override the default config directory with:

```bash
set ORIN_HOME=C:\path\to\custom\folder
```

Or specify a custom config file:

```bash
set ORIN_CONFIG_PATH=C:\path\to\config.toml
```

The configuration includes:

- user profile details
- LLM host and model settings
- voice preferences and TTS settings
- allowlisted folders for secure local access
- network-related preferences

## Security and Privacy

Orin is intentionally cautious around file access and actions:

- Only allowlisted directories are available for local search and file operations
- Sensitive actions may require confirmation
- Audit logs capture executed actions for review
- The app prefers local inference and local speech processing wherever possible

## Example Voice Commands

These are representative commands supported by the agent/router:

- "What can you do?"
- "Check system status"
- "What is my battery level?"
- "Mute audio"
- "Set volume to 75"
- "Open Notepad"
- "Launch Calculator"
- "Take a note: ..."
- "Show my notes"
- "Remind me to ..."
- "Search files for ..."
- "That's all" / "Goodbye"

## Development

Run tests:

```bash
pytest
```

Linting is configured through Ruff:

```bash
ruff check .
```

## License

This project is distributed under the MIT license. See the license file in the repository for details if present in your fork.

## Project Status

Orin is a local-first assistant prototype focused on privacy, offline operation, and safe desktop automation. It is actively structured around a modular design so the voice, router, tools, and security layers can evolve independently.

## Contributing

Contributions are welcome. If you are working on improvements, please:

1. Open or update an issue for significant changes
2. Keep features local-first and privacy-conscious
3. Add or update tests for behavior changes
4. Prefer small, focused pull requests

## Credits

Orin builds on a stack of local-first tools and libraries, including:

- Ollama for local LLM inference
- Python + Typer + Rich for the CLI
- pyttsx3 and Piper for offline speech synthesis
- Local indexing and search for safe file access
- Windows-native desktop behaviors for assistant automation

