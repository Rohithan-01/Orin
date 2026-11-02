"""Microphone audio capture, configurable push-to-talk hotkeys, and VAD recording."""

from __future__ import annotations

import ctypes
import re
import sys
import time
from typing import Any

import numpy as np
import sounddevice as sd

from orin.voice.vad import EnergyVAD

# Windows Virtual Key Codes
VK_MAP: dict[str, int] = {
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B,
    "space": 0x20,
    "ctrl": 0x11,
    "control": 0x11,
    "shift": 0x10,
    "alt": 0x12,
    "enter": 0x0D,
    "return": 0x0D,
}

if sys.platform == "win32":
    try:
        _GetAsyncKeyState = ctypes.windll.user32.GetAsyncKeyState
        _GetAsyncKeyState.argtypes = [ctypes.c_int]
        _GetAsyncKeyState.restype = ctypes.c_short
    except Exception:
        _GetAsyncKeyState = None
else:
    _GetAsyncKeyState = None


def parse_hotkey_string(hotkey_str: str) -> list[int]:
    """Parses hotkey descriptions (e.g. 'F9', 'F8', 'Ctrl+Space') into VK codes."""
    tokens = [t.strip().lower() for t in re.split(r"[+\-\s]+", hotkey_str) if t.strip()]
    vk_codes = [VK_MAP[t] for t in tokens if t in VK_MAP]
    return vk_codes or [0x78]  # Default to F9 (0x78)


def is_hotkey_pressed(hotkey_str: str = "F9") -> bool:
    """Checks whether the configured hotkey combination is actively pressed down."""
    if _GetAsyncKeyState is None:
        return False
    vk_codes = parse_hotkey_string(hotkey_str)
    try:
        # Most significant bit is set if the key is currently held down
        return all(bool(_GetAsyncKeyState(code) & 0x8000) for code in vk_codes)
    except Exception:
        return False


def is_f9_pressed() -> bool:
    """Backwards-compatible check for F9."""
    return is_hotkey_pressed("F9")


def is_terminal_enter_pressed() -> bool:
    """Non-blocking check if Enter or Space was pressed in the console terminal."""
    if sys.platform != "win32":
        return False
    try:
        import msvcrt

        if msvcrt.kbhit():
            ch = msvcrt.getch()
            # If special key prefix (0x00 or 0xE0), consume second byte
            if ch in (b"\x00", b"\xe0"):
                if msvcrt.kbhit():
                    msvcrt.getch()
                return False
            # Check Enter (CR / LF)
            if ch in (b"\r", b"\n"):
                return True
            # Check Spacebar in terminal
            if ch == b" ":
                return True
        return False
    except Exception:
        return False


def get_selected_mic_info(device_id: int | str | None = None) -> dict[str, Any]:
    """Returns metadata and health details about the chosen audio input device."""
    try:
        dev = sd.query_devices(device=device_id, kind="input")
        idx = sd.default.device[0] if device_id is None else device_id
        return {
            "index": idx,
            "name": dev.get("name", "Unknown Microphone"),
            "channels": dev.get("max_input_channels", 1),
            "sample_rate": int(dev.get("default_samplerate", 16000)),
            "host_api": dev.get("hostapi", 0),
        }
    except Exception as e:
        return {
            "index": -1,
            "name": f"Default Microphone ({e})",
            "channels": 1,
            "sample_rate": 16000,
            "host_api": 0,
        }


class AudioCapture:
    """Handles microphone recording with push-to-talk, tap-to-talk, and VAD silence detection."""

    def __init__(self, sample_rate: int = 16000, device: int | str | None = None) -> None:
        self.sample_rate = sample_rate
        self.device = device
        self.vad = EnergyVAD(sample_rate=sample_rate)

    def record_until_silence(
        self,
        silence_timeout: float = 1.2,
        max_duration: float = 25.0,
        interrupt_callback: Any = None,
    ) -> np.ndarray:
        """Records from the microphone until silence is detected or max duration reached."""
        frame_duration = 0.03  # 30 ms
        frame_size = int(self.sample_rate * frame_duration)
        chunks: list[np.ndarray] = []

        self.vad.reset()
        speech_started = False
        silence_start: float | None = None
        start_time = time.time()

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            device=self.device,
        ) as stream:
            while time.time() - start_time < max_duration:
                if interrupt_callback and interrupt_callback():
                    break

                frame, _ = stream.read(frame_size)
                chunks.append(frame)

                is_voice = self.vad.is_speech(frame)

                if is_voice:
                    speech_started = True
                    silence_start = None
                elif speech_started:
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start >= silence_timeout:
                        break

        if not chunks:
            return np.array([], dtype=np.float32)

        return np.concatenate(chunks, axis=0).flatten()

    def record_push_to_talk(
        self,
        max_duration: float = 25.0,
        interrupt_callback: Any = None,
        hotkey_str: str = "F9",
    ) -> np.ndarray:
        """Records audio while hotkey is held down OR until natural silence if key was tapped / Enter pressed."""
        frame_duration = 0.03
        frame_size = int(self.sample_rate * frame_duration)
        chunks: list[np.ndarray] = []
        start_time = time.time()
        speech_started = False
        silence_start: float | None = None
        key_held_initially = is_hotkey_pressed(hotkey_str)

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            device=self.device,
        ) as stream:
            while time.time() - start_time < max_duration:
                if interrupt_callback and interrupt_callback():
                    break

                frame, _ = stream.read(frame_size)
                chunks.append(frame)

                is_voice = self.vad.is_speech(frame)
                key_down = is_hotkey_pressed(hotkey_str)

                if is_voice:
                    speech_started = True
                    silence_start = None

                # Mode 1: User is actively holding down the hotkey (Push-To-Talk)
                if key_down:
                    key_held_initially = True
                    continue

                # Mode 2: Key was held during speech and now released
                if key_held_initially and not key_down and speech_started:
                    break

                # Mode 3: Key was tapped or Enter was pressed in terminal (Tap-to-Talk)
                if speech_started:
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start >= 1.2:
                        # Finished speaking
                        break
                else:
                    # User hasn't started speaking yet: allow up to 4.0s before aborting
                    if time.time() - start_time >= 4.0 and not key_down:
                        break

        if not chunks:
            return np.array([], dtype=np.float32)

        return np.concatenate(chunks, axis=0).flatten()


_global_audio_capture: AudioCapture | None = None


def get_audio_capture() -> AudioCapture:
    """Singleton getter for AudioCapture."""
    global _global_audio_capture
    if _global_audio_capture is None:
        _global_audio_capture = AudioCapture()
    return _global_audio_capture
