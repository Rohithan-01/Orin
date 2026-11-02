"""Voice Activity Detection (VAD) using adaptive energy and RMS thresholding."""

from __future__ import annotations

import numpy as np


class EnergyVAD:
    """Lightweight CPU-friendly Voice Activity Detector based on adaptive RMS energy.

    Uses zero external C dependencies and negligible CPU cycles (~0.1%).
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_duration_ms: int = 30,
        energy_threshold: float = 0.015,
        speech_pad_frames: int = 3,
    ) -> None:
        self.sample_rate = sample_rate
        self.frame_size = int(sample_rate * (frame_duration_ms / 1000.0))
        self.energy_threshold = energy_threshold
        self.speech_pad_frames = speech_pad_frames
        self.ambient_energy = 0.005
        self._speech_detected = False
        self._consecutive_speech = 0
        self._consecutive_silence = 0

    def compute_energy(self, frame: np.ndarray) -> float:
        """Computes Root-Mean-Square (RMS) amplitude of an audio frame."""
        if len(frame) == 0:
            return 0.0
        # Float32 audio expected between -1.0 and 1.0
        return float(np.sqrt(np.mean(frame**2)))

    def is_speech(self, frame: np.ndarray) -> bool:
        """Determines if the given audio frame contains human voice activity."""
        energy = self.compute_energy(frame)

        # Adapt ambient noise floor slowly during silence
        if energy < self.energy_threshold:
            self.ambient_energy = 0.95 * self.ambient_energy + 0.05 * energy
            dynamic_threshold = max(self.energy_threshold, self.ambient_energy * 2.5)
        else:
            dynamic_threshold = self.energy_threshold

        if energy > dynamic_threshold:
            self._consecutive_speech += 1
            self._consecutive_silence = 0
            if self._consecutive_speech >= self.speech_pad_frames:
                self._speech_detected = True
                return True
        else:
            self._consecutive_silence += 1
            self._consecutive_speech = 0
            if self._consecutive_silence >= self.speech_pad_frames * 2:
                self._speech_detected = False

        return self._speech_detected

    def reset(self) -> None:
        """Resets the detection state for a new turn."""
        self._speech_detected = False
        self._consecutive_speech = 0
        self._consecutive_silence = 0
