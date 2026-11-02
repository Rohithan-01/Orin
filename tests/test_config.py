"""Test suite for Orin configuration system."""

from pathlib import Path

from orin.config.settings import (
    OrinConfig,
    _serialize_config_to_toml,
    get_config,
    save_config,
)


def test_default_config() -> None:
    cfg = OrinConfig()
    assert cfg.llm.model == "llama3.2:3b"
    assert cfg.llm.num_ctx == 4096
    assert cfg.voice.engine == "pyttsx3"
    assert cfg.voice.rate == 170
    assert cfg.voice.hotkey == "F9"
    assert isinstance(cfg.security.allowlisted_folders, list)


def test_toml_serialization() -> None:
    cfg = OrinConfig()
    cfg.general.user_name = "TestUser"
    cfg.llm.model = "test-model"
    serialized = _serialize_config_to_toml(cfg)

    assert '[general]' in serialized
    assert 'user_name = "TestUser"' in serialized
    assert '[llm]' in serialized
    assert 'model = "test-model"' in serialized


def test_save_and_load_config(tmp_path: Path, monkeypatch) -> None:
    fake_config_file = tmp_path / "config.toml"
    monkeypatch.setenv("ORIN_CONFIG_PATH", str(fake_config_file))
    monkeypatch.setenv("ORIN_HOME", str(tmp_path))

    # Should create default config
    loaded_cfg = get_config()
    assert fake_config_file.exists()
    assert loaded_cfg.llm.model == "llama3.2:3b"

    # Modify and save
    loaded_cfg.general.user_name = "Alice"
    loaded_cfg.voice.rate = 190
    save_config(loaded_cfg)

    # Re-read
    reloaded_cfg = get_config()
    assert reloaded_cfg.general.user_name == "Alice"
    assert reloaded_cfg.voice.rate == 190
