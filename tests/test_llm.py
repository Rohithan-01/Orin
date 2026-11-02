"""Tests for LLM client, prompts, and agent conversation handling."""

from unittest.mock import MagicMock

from orin.core.agent import OrinAgent
from orin.core.prompts import build_system_prompt
from orin.llm.client import OllamaClient
from orin.memory.store import MemoryStore


def test_build_system_prompt() -> None:
    prompt = build_system_prompt(
        user_name="Rohithan",
        preferences={"drink": "green tea"},
        memory_summary="User likes local AI tools.",
    )
    assert "Rohithan" in prompt
    assert "green tea" in prompt
    assert "local AI tools" in prompt
    assert "Orin" in prompt


def test_extract_preference() -> None:
    client = OllamaClient()
    pref = client.extract_preference_if_any("Hello, call me Alex!")
    assert pref == ("user_name", "Alex")

    pref2 = client.extract_preference_if_any("my name is Jordan.")
    assert pref2 == ("user_name", "Jordan")

    no_pref = client.extract_preference_if_any("What is the weather today?")
    assert no_pref is None


def test_agent_turn_mocked_llm(tmp_path, monkeypatch) -> None:
    db_file = tmp_path / "test_agent.db"
    monkeypatch.setenv("ORIN_DB_PATH", str(db_file))

    mock_llm = MagicMock(spec=OllamaClient)
    # Simulate stream_chat yielding 3 tokens
    mock_llm.stream_chat.return_value = iter(["Hello", " there", "!"])
    mock_llm.extract_preference_if_any.return_value = None

    memory = MemoryStore()
    agent = OrinAgent(llm_client=mock_llm, memory_store=memory, session_id="test-agent")

    tokens = list(agent.handle_turn("Hi Orin"))
    assert tokens == ["Hello", " there", "!"]

    # Verify turns stored in memory
    turns = memory.get_recent_turns("test-agent")
    assert len(turns) == 2
    assert turns[0]["role"] == "user"
    assert turns[0]["content"] == "Hi Orin"
    assert turns[1]["role"] == "assistant"
    assert turns[1]["content"] == "Hello there!"
