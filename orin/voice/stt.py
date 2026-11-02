"""Speech-to-Text (STT) transcription engine using faster-whisper on CPU."""

from __future__ import annotations

import os
import re
from typing import Any

import numpy as np

# Suppress symlink warnings on Windows
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# Hallucinations common in Whisper on low audio/silence
COMMON_WHISPER_HALLUCINATIONS = {
    "thank you",
    "thank you.",
    "thanks for watching",
    "thanks for watching.",
    "subtitles by",
    "[blank_audio]",
    "(bell dings)",
    "you",
    "bye",
}


class WhisperTranscriber:
    """CPU-optimized local speech transcriber using faster-whisper base model in int8."""

    def __init__(self, model_size: str = "base", compute_type: str = "int8") -> None:
        self.model_size = model_size
        self.compute_type = compute_type
        self._model: Any = None

    def _ensure_loaded(self) -> Any:
        """Lazy-loads the WhisperModel to ensure instant CLI startup."""
        if self._model is None:
            from faster_whisper import WhisperModel

            # Run on CPU with 4 threads for optimal Ryzen 5 5500U performance
            self._model = WhisperModel(
                self.model_size,
                device="cpu",
                compute_type=self.compute_type,
                cpu_threads=4,
                num_workers=1,
            )
        return self._model

    def is_loaded(self) -> bool:
        """Returns True if the model is already in memory."""
        return self._model is not None

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribes float32 16kHz audio array into text.

        Returns clean text or empty string if no valid speech was present.
        """
        if len(audio) == 0:
            return ""

        # Check for near-zero audio (silence)
        rms = float(np.sqrt(np.mean(audio**2)))
        if rms < 0.003:
            return ""

        model = self._ensure_loaded()
        try:
            # Flatten to 1D if needed
            if audio.ndim > 1:
                audio = audio.flatten()

            segments, _ = model.transcribe(
                audio,
                language="en",
                beam_size=1,  # Fastest beam size for responsive real-time conversation
                temperature=0.0,
                vad_filter=True,
            )

            texts = [s.text.strip() for s in segments if s.text]
            full_text = " ".join(texts).strip()

            # Clean and filter common hallucinations
            lower = full_text.lower().strip(" .!?,")
            if lower in COMMON_WHISPER_HALLUCINATIONS or len(lower) < 2:
                return ""

            # Remove multiple spaces
            return re.sub(r"\s+", " ", full_text).strip()
        except Exception:
            return ""


_global_transcriber: WhisperTranscriber | None = None


def get_transcriber() -> WhisperTranscriber:
    """Singleton getter for WhisperTranscriber."""
    global _global_transcriber
    if _global_transcriber is None:
        _global_transcriber = WhisperTranscriber()
    return _global_transcriber
