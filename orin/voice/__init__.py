"""Voice synthesis, recognition, and audio capture subsystem."""

from orin.voice.audio import (
    AudioCapture,
    get_audio_capture,
    get_selected_mic_info,
    is_f9_pressed,
    is_hotkey_pressed,
    is_terminal_enter_pressed,
    parse_hotkey_string,
)
from orin.voice.stt import WhisperTranscriber, get_transcriber
from orin.voice.tts import (
    FEMALE_VOICE_PRIORITY,
    SentenceSplitter,
    TTSPlayer,
    download_piper_voice,
    find_best_female_sapi_voice,
    get_effective_voice_id,
    get_tts_player,
    handle_voice_command,
    prepare_text_for_speech,
)
from orin.voice.vad import EnergyVAD

__all__ = [
    "AudioCapture",
    "EnergyVAD",
    "FEMALE_VOICE_PRIORITY",
    "SentenceSplitter",
    "TTSPlayer",
    "WhisperTranscriber",
    "download_piper_voice",
    "find_best_female_sapi_voice",
    "get_effective_voice_id",
    "get_audio_capture",
    "get_selected_mic_info",
    "get_transcriber",
    "get_tts_player",
    "handle_voice_command",
    "is_f9_pressed",
    "is_hotkey_pressed",
    "is_terminal_enter_pressed",
    "parse_hotkey_string",
    "prepare_text_for_speech",
]
