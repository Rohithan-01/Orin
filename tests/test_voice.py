"""Tests for Voice Reply subsystem, female voice selection, and sentence streaming."""

from unittest.mock import MagicMock

from orin.config.settings import OrinConfig
from orin.voice.tts import (
    SentenceSplitter,
    TTSPlayer,
    find_best_female_sapi_voice,
    handle_voice_command,
    prepare_text_for_speech,
)


def test_female_voice_selection_never_picks_male(monkeypatch) -> None:
    # Mock pyttsx3 voices containing both David and Zira
    mock_voice_david = MagicMock()
    mock_voice_david.id = "TTS_MS_EN-US_DAVID_11.0"
    mock_voice_david.name = "Microsoft David Desktop - English (United States)"

    mock_voice_zira = MagicMock()
    mock_voice_zira.id = "TTS_MS_EN-US_ZIRA_11.0"
    mock_voice_zira.name = "Microsoft Zira Desktop - English (United States)"

    mock_engine = MagicMock()
    # Even if David is listed first in SAPI
    mock_engine.getProperty.return_value = [mock_voice_david, mock_voice_zira]

    import pyttsx3
    monkeypatch.setattr(pyttsx3, "init", lambda: mock_engine)

    voice_id, voice_name = find_best_female_sapi_voice()
    # Must select Zira, never David
    assert voice_id == "TTS_MS_EN-US_ZIRA_11.0"
    assert "Zira" in voice_name


def test_prepare_text_for_speech() -> None:
    text = (
        "Here is the function:\n"
        "```python\ndef hello():\n    return 'world'\n```\n"
        "Visit https://github.com/project or check C:\\Users\\User\\Documents\\report.docx for details."
    )
    cleaned = prepare_text_for_speech(text)

    # Code block replaced
    assert "Here is the code shown on your screen" in cleaned
    assert "def hello" not in cleaned

    # URL replaced
    assert "https://" not in cleaned
    assert "link" in cleaned

    # File path shortened
    assert "C:\\Users" not in cleaned
    assert "report.docx" in cleaned


def test_sentence_splitter() -> None:
    splitter = SentenceSplitter()

    # Feed token by token
    tokens = ["Hello", " world", ". ", "How ", "are ", "you", "? ", "This is Dr. Smith calling."]
    sentences: list[str] = []

    for t in tokens:
        sentences.extend(splitter.add_token(t))

    sentences.extend(splitter.flush())

    assert len(sentences) == 3
    assert sentences[0] == "Hello world."
    assert sentences[1] == "How are you?"
    # Dr. Smith should not be split at "Dr."
    assert sentences[2] == "This is Dr. Smith calling."


def test_voice_commands() -> None:
    cfg = OrinConfig()
    cfg.voice.rate = 170
    cfg.voice.muted = False

    # Test speak slower
    msg = handle_voice_command("speak slower", cfg)
    assert msg is not None
    assert cfg.voice.rate == 150

    # Test speak faster
    msg = handle_voice_command("speak faster", cfg)
    assert msg is not None
    assert cfg.voice.rate == 170

    # Test mute voice
    msg = handle_voice_command("mute voice", cfg)
    assert msg is not None
    assert cfg.voice.muted is True

    # Test unmute voice
    msg = handle_voice_command("unmute voice", cfg)
    assert msg is not None
    assert cfg.voice.muted is False


def test_tts_player_interrupt() -> None:
    cfg = OrinConfig()
    player = TTSPlayer(config=cfg)

    player.enqueue_sentence("Test sentence one.")
    player.enqueue_sentence("Test sentence two.")

    # Interrupt clears queue
    player.interrupt()
    assert player.sentence_queue.empty()
    assert player.interrupt_event.is_set()
