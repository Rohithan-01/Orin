"""Tests for Voice Activity Detection (VAD) and faster-whisper STT transcriber."""

import numpy as np

from orin.cli.console import format_voice_state_bar
from orin.voice.audio import is_f9_pressed
from orin.voice.stt import WhisperTranscriber
from orin.voice.vad import EnergyVAD


def test_energy_vad_silence() -> None:
    vad = EnergyVAD(sample_rate=16000, frame_duration_ms=30)
    # Silent frame
    silent_frame = np.zeros(480, dtype=np.float32)
    assert vad.compute_energy(silent_frame) == 0.0
    assert not vad.is_speech(silent_frame)


def test_energy_vad_speech() -> None:
    vad = EnergyVAD(sample_rate=16000, frame_duration_ms=30, energy_threshold=0.01)
    # Synthetic speech wave
    t = np.linspace(0, 0.03, 480, endpoint=False)
    speech_frame = (0.2 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)

    assert vad.compute_energy(speech_frame) > 0.05
    # Consecutive speech triggers speech detected
    for _ in range(5):
        vad.is_speech(speech_frame)
    assert vad.is_speech(speech_frame) is True


def test_stt_silence_handling() -> None:
    stt = WhisperTranscriber()
    # Empty audio
    assert stt.transcribe(np.array([], dtype=np.float32)) == ""

    # Silent audio (zeros)
    silent_audio = np.zeros(16000, dtype=np.float32)
    assert stt.transcribe(silent_audio) == ""


def test_f9_key_check() -> None:
    # Function should return a boolean without throwing exceptions
    pressed = is_f9_pressed()
    assert isinstance(pressed, bool)


def test_hotkey_parsing_and_detection() -> None:
    from orin.voice.audio import (
        get_selected_mic_info,
        is_hotkey_pressed,
        is_terminal_enter_pressed,
        parse_hotkey_string,
    )

    # Test hotkey parsing
    assert parse_hotkey_string("F9") == [0x78]
    assert parse_hotkey_string("F8") == [0x77]
    assert parse_hotkey_string("Ctrl+Space") == [0x11, 0x20]
    assert parse_hotkey_string("Ctrl-Space") == [0x11, 0x20]

    # Test key checking functions return bool without exceptions
    assert isinstance(is_hotkey_pressed("F9"), bool)
    assert isinstance(is_hotkey_pressed("F8"), bool)
    assert isinstance(is_hotkey_pressed("Ctrl+Space"), bool)
    assert isinstance(is_terminal_enter_pressed(), bool)

    # Test microphone info
    mic_info = get_selected_mic_info()
    assert "name" in mic_info
    assert "index" in mic_info


def test_voice_state_bar_rendering() -> None:
    for state in ("IDLE", "LISTENING", "THINKING", "SPEAKING"):
        panel = format_voice_state_bar(state=state, online=True, model="llama3.2:3b", hotkey="F8")
        assert panel is not None
