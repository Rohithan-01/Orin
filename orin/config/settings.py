"""Orin configuration settings and persistence using TOML."""

from __future__ import annotations

import getpass
import os
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


def get_default_config_dir() -> Path:
    """Returns the default configuration directory (~/.orin)."""
    override = os.environ.get("ORIN_HOME")
    if override:
        return Path(override).resolve()
    return Path.home() / ".orin"


def get_default_allowlisted_folders() -> list[str]:
    """Returns default user folders to allowlist on Windows."""
    user_home = Path.home()
    folders = [
        str(user_home / "Documents"),
        str(user_home / "Desktop"),
        str(user_home / "Downloads"),
    ]
    # Filter to existing directories
    existing = [f for f in folders if Path(f).exists()]
    return existing if existing else [str(user_home)]


class GeneralConfig(BaseModel):
    user_name: str = Field(default_factory=lambda: getpass.getuser().capitalize())
    first_run: bool = True
    debug: bool = False


class LLMConfig(BaseModel):
    host: str = "http://localhost:11434"
    model: str = "llama3.2:3b"
    num_ctx: int = 4096
    keep_alive: str = "10m"
    temperature: float = 0.7


class VoiceConfig(BaseModel):
    engine: str = "pyttsx3"  # "pyttsx3" or "piper"
    voice_id: str = ""       # empty or ID of chosen voice
    rate: int = 170          # natural words per minute (about 170 wpm)
    volume: float = 1.0      # 0.0 to 1.0
    muted: bool = False
    hotkey: str = "F9"
    stt_model: str = "base"
    stt_compute: str = "int8"
    wake_word_enabled: bool = False
    wake_word: str = "hey orin"


class SecurityConfig(BaseModel):
    allowlisted_folders: list[str] = Field(default_factory=get_default_allowlisted_folders)
    ask_confirmation_medium: bool = False
    ask_confirmation_high: bool = True
    audit_log_enabled: bool = True


class NetworkConfig(BaseModel):
    check_interval_seconds: int = 10
    weather_location: str = ""
    mail_imap_server: str = ""
    mail_email: str = ""
    whatsapp_contacts_file: str = "contacts.json"


class OrinConfig(BaseModel):
    general: GeneralConfig = Field(default_factory=GeneralConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    network: NetworkConfig = Field(default_factory=NetworkConfig)


def get_config_dir() -> Path:
    """Returns the config directory, ensuring it exists."""
    config_dir = get_default_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    """Returns path to the config.toml file."""
    custom_path = os.environ.get("ORIN_CONFIG_PATH")
    if custom_path:
        return Path(custom_path).resolve()
    return get_config_dir() / "config.toml"


def _format_toml_value(val: Any) -> str:
    """Format python primitive value to TOML string representation."""
    if isinstance(val, bool):
        return "true" if val else "false"
    elif isinstance(val, (int, float)):
        return str(val)
    elif isinstance(val, str):
        escaped = val.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    elif isinstance(val, list):
        items = ", ".join(_format_toml_value(x) for x in val)
        return f"[{items}]"
    return f'"{val}"'


def _serialize_config_to_toml(cfg: OrinConfig) -> str:
    """Serialize OrinConfig into a clean, well-commented TOML string."""
    lines = [
        "# ====================================================================",
        "# Orin Configuration File",
        "# Lightweight Local-First Voice Assistant for Windows",
        "# ====================================================================",
        "",
        "[general]",
        f"user_name = {_format_toml_value(cfg.general.user_name)}",
        f"first_run = {_format_toml_value(cfg.general.first_run)}",
        f"debug = {_format_toml_value(cfg.general.debug)}",
        "",
        "[llm]",
        "# Ollama host endpoint and model settings",
        f"host = {_format_toml_value(cfg.llm.host)}",
        f"model = {_format_toml_value(cfg.llm.model)}",
        f"num_ctx = {_format_toml_value(cfg.llm.num_ctx)}",
        f"keep_alive = {_format_toml_value(cfg.llm.keep_alive)}",
        f"temperature = {_format_toml_value(cfg.llm.temperature)}",
        "",
        "[voice]",
        "# TTS engine: 'pyttsx3' (Windows SAPI offline) or 'piper'",
        f"engine = {_format_toml_value(cfg.voice.engine)}",
        f"voice_id = {_format_toml_value(cfg.voice.voice_id)}",
        f"rate = {_format_toml_value(cfg.voice.rate)}",
        f"volume = {_format_toml_value(cfg.voice.volume)}",
        f"muted = {_format_toml_value(cfg.voice.muted)}",
        f"hotkey = {_format_toml_value(cfg.voice.hotkey)}",
        f"stt_model = {_format_toml_value(cfg.voice.stt_model)}",
        f"stt_compute = {_format_toml_value(cfg.voice.stt_compute)}",
        f"wake_word_enabled = {_format_toml_value(cfg.voice.wake_word_enabled)}",
        f"wake_word = {_format_toml_value(cfg.voice.wake_word)}",
        "",
        "[security]",
        "# Only allowlisted directories can be read, written, or searched",
        f"allowlisted_folders = {_format_toml_value(cfg.security.allowlisted_folders)}",
        f"ask_confirmation_medium = {_format_toml_value(cfg.security.ask_confirmation_medium)}",
        f"ask_confirmation_high = {_format_toml_value(cfg.security.ask_confirmation_high)}",
        f"audit_log_enabled = {_format_toml_value(cfg.security.audit_log_enabled)}",
        "",
        "[network]",
        f"check_interval_seconds = {_format_toml_value(cfg.network.check_interval_seconds)}",
        f"weather_location = {_format_toml_value(cfg.network.weather_location)}",
        f"mail_imap_server = {_format_toml_value(cfg.network.mail_imap_server)}",
        f"mail_email = {_format_toml_value(cfg.network.mail_email)}",
        f"whatsapp_contacts_file = {_format_toml_value(cfg.network.whatsapp_contacts_file)}",
        "",
    ]
    return "\n".join(lines)


def get_config() -> OrinConfig:
    """Load configuration from ~/.orin/config.toml, creating default with female voice if not exists."""
    config_file = get_config_path()
    if not config_file.exists():
        cfg = OrinConfig()
        try:
            from orin.voice.tts import find_best_female_sapi_voice

            voice_id, _ = find_best_female_sapi_voice()
            if voice_id:
                cfg.voice.voice_id = voice_id
        except Exception:
            pass
        save_config(cfg)
        return cfg

    try:
        with open(config_file, "rb") as f:
            data = tomllib.load(f)
        cfg = OrinConfig(**data)
        if not cfg.voice.voice_id:
            try:
                from orin.voice.tts import find_best_female_sapi_voice

                voice_id, _ = find_best_female_sapi_voice()
                if voice_id:
                    cfg.voice.voice_id = voice_id
                    save_config(cfg)
            except Exception:
                pass
        return cfg
    except Exception:
        # If parsing fails, fall back to default
        return OrinConfig()


def save_config(cfg: OrinConfig) -> None:
    """Save configuration to ~/.orin/config.toml."""
    config_file = get_config_path()
    config_file.parent.mkdir(parents=True, exist_ok=True)
    content = _serialize_config_to_toml(cfg)
    config_file.write_text(content, encoding="utf-8")
