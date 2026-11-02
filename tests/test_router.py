"""Tests for Orin intent classifier, tool dispatcher, and agent integration."""

import threading
from pathlib import Path

import pytest

from orin.config.settings import OrinConfig
from orin.core.agent import OrinAgent
from orin.core.router import (
    IntentClassifier,
    IntentDispatcher,
    IntentType,
)
from orin.llm.client import OllamaClient
from orin.memory.store import MemoryStore
from orin.voice.tts import TTSPlayer


class FakeLLMClient(OllamaClient):
    """Test fake for LLM client."""

    def __init__(self) -> None:
        pass

    def stream_chat(self, messages, timeout=60.0):
        yield "Hello there! "
        yield "How can I help you today?"

    def chat(self, messages, timeout=60.0):
        return "Chat response"

    def extract_preference_if_any(self, user_text: str):
        return None

    def summarize_conversation(self, turns):
        return "Summary"


class FakeTTSPlayer(TTSPlayer):
    """Test fake for TTS."""

    def __init__(self) -> None:
        self.spoken = []
        self.interrupt_event = threading.Event()

    def enqueue_sentence(self, sentence: str) -> None:
        self.spoken.append(sentence)

    def interrupt(self) -> None:
        self.interrupt_event.set()


def test_intent_classifier_patterns() -> None:
    classifier = IntentClassifier()

    # Battery
    intent = classifier.classify("What is my battery level?")
    assert intent.intent_type == IntentType.SYSTEM_STATS
    assert intent.parameters.get("target") == "battery"

    # System stats
    intent = classifier.classify("Check system health and CPU usage")
    assert intent.intent_type == IntentType.SYSTEM_STATS

    # Volume
    intent = classifier.classify("Mute audio")
    assert intent.intent_type == IntentType.VOLUME_CONTROL
    assert intent.parameters.get("action") == "mute"

    intent = classifier.classify("Set volume to 75")
    assert intent.intent_type == IntentType.VOLUME_CONTROL
    assert intent.parameters.get("level") == 75

    # App launch
    intent = classifier.classify("Open notepad")
    assert intent.intent_type == IntentType.APP_LAUNCH
    assert intent.parameters.get("app_name") == "notepad"

    # Notes
    intent = classifier.classify("Take a note: Buy groceries tomorrow")
    assert intent.intent_type == IntentType.NOTE_CREATE
    assert intent.parameters.get("content") == "Buy groceries tomorrow"

    intent = classifier.classify("Show my notes")
    assert intent.intent_type == IntentType.NOTE_LIST

    # Reminders
    intent = classifier.classify("Remind me to call Mom at 6pm")
    assert intent.intent_type == IntentType.REMINDER_CREATE
    assert intent.parameters.get("message") == "call Mom at 6pm"

    intent = classifier.classify("Show my reminders")
    assert intent.intent_type == IntentType.REMINDER_LIST

    # Conversational fallback
    intent = classifier.classify("What is the capital of France?")
    assert intent.intent_type == IntentType.CONVERSATION


def test_intent_dispatcher(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    test_db = tmp_path / "test_dispatch.db"
    monkeypatch.setenv("ORIN_DB_PATH", str(test_db))

    cfg = OrinConfig()
    dispatcher = IntentDispatcher(config=cfg)

    # Dispatch battery
    intent_bat = IntentClassifier().classify("Check battery level")
    res_bat = dispatcher.dispatch(intent_bat)
    assert res_bat.handled is True
    assert "battery" in res_bat.spoken_response.lower()

    # Dispatch note creation
    intent_note = IntentClassifier().classify("Take a note: Schedule dentist appointment")
    res_note = dispatcher.dispatch(intent_note)
    assert res_note.handled is True
    assert "saved that note" in res_note.spoken_response.lower()

    # Dispatch conversation (must NOT be handled by dispatcher, left for LLM)
    intent_chat = IntentClassifier().classify("Tell me a story about a space traveler")
    res_chat = dispatcher.dispatch(intent_chat)
    assert res_chat.handled is False


def test_agent_handle_turn_with_router(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    test_db = tmp_path / "test_agent_router.db"
    monkeypatch.setenv("ORIN_DB_PATH", str(test_db))

    cfg = OrinConfig()
    memory = MemoryStore()
    fake_llm = FakeLLMClient()
    fake_tts = FakeTTSPlayer()

    agent = OrinAgent(
        config=cfg,
        llm_client=fake_llm,
        memory_store=memory,
        tts_player=fake_tts,
        speak_by_default=True,
    )

    # 1. Turn routed to tool (battery)
    tokens_tool = list(agent.handle_turn("Check battery status"))
    full_tool_reply = "".join(tokens_tool)
    assert "battery" in full_tool_reply.lower()
    assert len(fake_tts.spoken) >= 1

    # 2. Turn routed to general conversation (LLM)
    tokens_llm = list(agent.handle_turn("Tell me something interesting"))
    full_llm_reply = "".join(tokens_llm)
    assert "Hello there!" in full_llm_reply
