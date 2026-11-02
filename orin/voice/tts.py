"""Text-to-Speech (TTS) engine with female voice default, sentence streaming, and interruption."""

from __future__ import annotations

import logging
import queue
import re
import threading
import time
from pathlib import Path

import httpx

from orin.config.settings import OrinConfig, get_config, get_config_dir, save_config

logger = logging.getLogger(__name__)

# Priority order for female Windows SAPI voices
FEMALE_VOICE_PRIORITY = ["zira", "heera", "hazel", "aria"]
MALE_KEYWORDS = ["david", "mark", "george", "paul", "richard", "james"]

PIPER_FEMALE_VOICES = {
    "amy": {
        "name": "en_US-amy-medium",
        "onnx_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx",
        "json_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json",
    },
    "hfc_female": {
        "name": "en_US-hfc_female-medium",
        "onnx_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/hfc_female/medium/en_US-hfc_female-medium.onnx",
        "json_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/hfc_female/medium/en_US-hfc_female-medium.onnx.json",
    },
    "jenny": {
        "name": "en_GB-jenny_dioco-medium",
        "onnx_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/jenny_dioco/medium/en_GB-jenny_dioco-medium.onnx",
        "json_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/jenny_dioco/medium/en_GB-jenny_dioco-medium.onnx.json",
    },
}


def get_piper_voices_dir() -> Path:
    """Directory where downloaded Piper neural voices are stored (~/.orin/voices/piper)."""
    p = get_config_dir() / "voices" / "piper"
    p.mkdir(parents=True, exist_ok=True)
    return p


def find_best_female_sapi_voice() -> tuple[str, str]:
    """Finds the best female Windows SAPI voice in priority order (Zira, Heera, Hazel, Aria).

    NEVER defaults to a male voice (David, Mark, etc.) if any other voice exists.
    Returns (voice_id, voice_name).
    """
    try:
        import pyttsx3

        engine = pyttsx3.init()
        voices = engine.getProperty("voices") or []

        # 1. Check priority list first
        for target in FEMALE_VOICE_PRIORITY:
            for v in voices:
                name_lower = v.name.lower()
                if target in name_lower:
                    return v.id, v.name

        # 2. Check for gender attribute or 'female' in ID/name
        for v in voices:
            name_lower = v.name.lower()
            gender = getattr(v, "gender", "").lower()
            if "female" in gender or "female" in name_lower:
                return v.id, v.name

        # 3. Reject any voice matching male keywords if possible
        for v in voices:
            name_lower = v.name.lower()
            if not any(male in name_lower for male in MALE_KEYWORDS):
                return v.id, v.name

        # Fallback to first voice if no other option
        if voices:
            return voices[0].id, voices[0].name
    except Exception:
        pass
    return "", "System Default"


def prepare_text_for_speech(text: str) -> str:
    """Cleans up text for spoken output.

    - Replaces code blocks with a brief audio notice.
    - Replaces raw URLs with 'link'.
    - Replaces long file paths with just the filename.
    - Strips markdown formatting characters.
    """
    # 1. Replace multi-line code blocks
    cleaned = re.sub(
        r"```[\w-]*\n[\s\S]*?```",
        " Here is the code shown on your screen. ",
        text,
    )
    # 2. Replace inline code snippets
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)

    # 3. Replace markdown links [label](url) with label
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)

    # 4. Replace raw URLs
    cleaned = re.sub(r"https?://\S+", " link ", cleaned)

    # 5. Shorten Windows absolute paths (e.g. C:\Users\...\document.pdf -> document.pdf)
    cleaned = re.sub(r"[A-Za-z]:\\[\w\-\\]+\\([\w\.\-]+)", r"\1", cleaned)

    # 6. Remove markdown bold/italic/headers/bullet asterisks
    cleaned = re.sub(r"[*#_~>]+", " ", cleaned)

    # 7. Normalize multiple whitespaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


class SentenceSplitter:
    """Accumulates streamed tokens and emits clean, complete sentences."""

    def __init__(self) -> None:
        self.buffer = ""
        # Matches sentence endings followed by space, quote, or newline
        self._boundary_re = re.compile(r"([.!?])(?:\s+|$|\n)")
        # Common abbreviations to avoid false splits
        self._abbreviations = ("dr.", "mr.", "mrs.", "ms.", "e.g.", "i.e.", "vs.", "etc.")

    def add_token(self, token: str) -> list[str]:
        """Adds a token and returns any complete sentences ready to be spoken."""
        self.buffer += token
        sentences: list[str] = []

        while True:
            match = self._boundary_re.search(self.buffer)
            if not match:
                break

            end_pos = match.end()
            candidate = self.buffer[:end_pos].strip()

            # Check if this boundary is inside an abbreviation
            last_word = candidate.split()[-1].lower() if candidate.split() else ""
            if any(last_word.endswith(abbr) for abbr in self._abbreviations):
                # Search further after this match
                break

            if candidate:
                cleaned = prepare_text_for_speech(candidate)
                if cleaned:
                    sentences.append(cleaned)

            self.buffer = self.buffer[end_pos:]

        return sentences

    def flush(self) -> list[str]:
        """Flushes any remaining text in the buffer as the final sentence."""
        remaining = self.buffer.strip()
        self.buffer = ""
        if remaining:
            cleaned = prepare_text_for_speech(remaining)
            if cleaned:
                return [cleaned]
        return []


def get_effective_voice_id(config: OrinConfig | None = None) -> tuple[str, str]:
    """Returns (voice_id, voice_name), guaranteeing Microsoft Zira / female voice over David."""
    cfg = config or get_config()
    vid = cfg.voice.voice_id
    if vid and not any(male in vid.lower() for male in MALE_KEYWORDS):
        name = vid.split("\\")[-1]
        return vid, name
    return find_best_female_sapi_voice()


class TTSPlayer:
    """Background interruptible TTS playback queue supporting pyttsx3 and Piper.

    Uses a dedicated background worker thread with a fresh pyttsx3 engine
    per utterance, preventing SAPI5 COM state desync / speech blocking after
    the first reply.
    """

    def __init__(self, config: OrinConfig | None = None) -> None:
        self.config = config or get_config()
        self.sentence_queue: queue.Queue[str | None] = queue.Queue()
        self.interrupt_event = threading.Event()
        self.worker_thread: threading.Thread | None = None
        self._running = False
        self._is_speaking = False

    def start(self) -> None:
        """Starts the background audio playback thread."""
        if self._running:
            return
        self._running = True
        self.interrupt_event.clear()
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def stop(self) -> None:
        """Stops the worker thread completely."""
        self.interrupt()
        self._running = False
        self.sentence_queue.put(None)
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=1.0)

    def interrupt(self) -> None:
        """Immediately interrupts any current speech and clears remaining sentences."""
        self.interrupt_event.set()
        while not self.sentence_queue.empty():
            try:
                self.sentence_queue.get_nowait()
                self.sentence_queue.task_done()
            except (queue.Empty, ValueError):
                break
        self._is_speaking = False

    def is_speaking(self) -> bool:
        """Returns True if audio is actively playing or sentences are queued."""
        return self._is_speaking or not self.sentence_queue.empty()

    def wait_until_finished(self, timeout: float = 30.0) -> bool:
        """Blocks until the sentence queue is empty and playback completes."""
        start = time.time()
        time.sleep(0.08)
        while self.is_speaking():
            if self.interrupt_event.is_set():
                break
            if time.time() - start > timeout:
                return False
            time.sleep(0.04)
        return True

    def enqueue_sentence(self, sentence: str) -> None:
        """Enqueues a sentence to be spoken out loud."""
        if not sentence or not sentence.strip():
            return
        if self.config.voice.muted:
            return
        self.interrupt_event.clear()
        self.sentence_queue.put(sentence.strip())

    def _worker_loop(self) -> None:
        """Worker loop initializing fresh pyttsx3 engine per utterance for 100% reliability."""
        while self._running:
            try:
                sentence = self.sentence_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if sentence is None:
                break

            if self.interrupt_event.is_set():
                self.sentence_queue.task_done()
                continue

            self._is_speaking = True
            logger.info("speaking started: %s", sentence)
            try:
                import pythoncom

                pythoncom.CoInitialize()

                import pyttsx3

                engine = pyttsx3.init()

                voice_id, _ = get_effective_voice_id(self.config)
                if voice_id:
                    try:
                        engine.setProperty("voice", voice_id)
                    except Exception:
                        pass

                engine.setProperty("rate", self.config.voice.rate or 170)
                engine.setProperty("volume", self.config.voice.volume or 1.0)

                engine.say(sentence)
                engine.runAndWait()
                del engine

                pythoncom.CoUninitialize()

                # Natural pause between sentences (120ms)
                time.sleep(0.12)
            except Exception as e:
                logger.error("TTS error: %s", e)
            finally:
                logger.info("speaking finished: %s", sentence)
                self._is_speaking = False
                self.sentence_queue.task_done()


def download_piper_voice(key: str = "amy") -> tuple[Path, Path] | None:
    """Downloads a Piper female voice (.onnx and .onnx.json) if not already cached."""
    if key not in PIPER_FEMALE_VOICES:
        return None

    info = PIPER_FEMALE_VOICES[key]
    dest_dir = get_piper_voices_dir()
    onnx_path = dest_dir / f"{info['name']}.onnx"
    json_path = dest_dir / f"{info['name']}.onnx.json"

    if onnx_path.exists() and json_path.exists():
        return onnx_path, json_path

    try:
        with httpx.Client(follow_redirects=True, timeout=60.0) as client:
            # Download json
            r_json = client.get(info["json_url"])
            if r_json.status_code == 200:
                json_path.write_bytes(r_json.content)

            # Download onnx model
            r_onnx = client.get(info["onnx_url"])
            if r_onnx.status_code == 200:
                onnx_path.write_bytes(r_onnx.content)

        if onnx_path.exists() and json_path.exists():
            return onnx_path, json_path
    except Exception:
        pass
    return None


def handle_voice_command(user_text: str, config: OrinConfig | None = None) -> str | None:
    """Handles natural voice control commands ('speak slower', 'speak faster', 'mute voice', etc.)."""
    if config is None:
        config = get_config()

    lower = user_text.lower().strip()

    if "speak slower" in lower or "talk slower" in lower:
        config.voice.rate = max(110, config.voice.rate - 20)
        save_config(config)
        return f"Speaking slower now, at {config.voice.rate} words per minute."

    if "speak faster" in lower or "talk faster" in lower:
        config.voice.rate = min(240, config.voice.rate + 20)
        save_config(config)
        return f"Speaking faster now, at {config.voice.rate} words per minute."

    if "unmute voice" in lower or "turn on voice" in lower:
        config.voice.muted = False
        save_config(config)
        return "Voice unmuted. I'm ready to speak out loud."

    if "mute voice" in lower or "turn off voice" in lower or "silence voice" in lower:
        config.voice.muted = True
        save_config(config)
        return "Voice muted. I will respond only in text on screen."

    if "change voice" in lower or "switch voice" in lower:
        # Cycle through voices
        try:
            import pyttsx3

            engine = pyttsx3.init()
            voices = engine.getProperty("voices") or []
            if len(voices) > 1:
                curr = config.voice.voice_id
                next_v = voices[0]
                for idx, v in enumerate(voices):
                    if v.id == curr and idx + 1 < len(voices):
                        next_v = voices[idx + 1]
                        break
                config.voice.voice_id = next_v.id
                save_config(config)
                return f"Voice switched to {next_v.name}."
        except Exception:
            pass

    return None


_global_tts_player: TTSPlayer | None = None


def get_tts_player() -> TTSPlayer:
    """Singleton getter for active TTSPlayer."""
    global _global_tts_player
    if _global_tts_player is None:
        _global_tts_player = TTSPlayer()
        _global_tts_player.start()
    return _global_tts_player
