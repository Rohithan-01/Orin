"""Verification script testing a full 6-turn conversation with Orin with speech out loud."""

import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("test_six_turns")

from orin.config.settings import get_config
from orin.core.agent import OrinAgent
from orin.voice.tts import get_effective_voice_id


def run_six_turns() -> None:
    print("=" * 70)
    print("ORIN 6-TURN CONVERSATION VERIFICATION TEST")
    print("=" * 70)

    config = get_config()
    voice_id, voice_name = get_effective_voice_id(config)
    print(f"Configured Voice: '{voice_name}' (ID: {voice_id})")
    print(f"Configured TTS Engine: {config.voice.engine}")
    print(f"Configured Speech Rate: {config.voice.rate} wpm\n")

    agent = OrinAgent(config=config, speak_by_default=True)
    agent.tts.start()

    turns = [
        "what can you do",
        "what is my battery level",
        "take a note: buy groceries tomorrow",
        "show my notes",
        "check system status",
        "tell me a one sentence motivational tip",
    ]

    spoken_turns: list[int] = []

    for i, user_text in enumerate(turns, 1):
        print("\n" + "-" * 70)
        print(f"--- TURN {i} OF 6 ---")
        print(f"User: '{user_text}'")
        print("-" * 70)

        # Stage 1: Listening
        logger.info("listening started")
        print(f"[STAGE: LISTENING STARTED] Processing input for turn {i}...")

        time.sleep(0.3)

        # Stage 2: Speaking
        logger.info("speaking started")
        print(f"[STAGE: SPEAKING STARTED] Orin voice synthesis started for turn {i}...")
        print("Orin: ", end="", flush=True)

        tokens: list[str] = []
        for token in agent.handle_turn(user_text, speak=True):
            print(token, end="", flush=True)
            tokens.append(token)
        print()

        full_reply = "".join(tokens).strip()
        print(f"[REPLY TEXT] '{full_reply}'")

        # Wait for audio to finish playing out loud
        finished = agent.tts.wait_until_finished(timeout=25.0)
        logger.info("speaking finished")
        print(f"[STAGE: SPEAKING FINISHED] Turn {i} audio playback complete (success={finished})")

        if finished and full_reply:
            spoken_turns.append(i)

    print("\n" + "=" * 70)
    print("6-TURN TEST RESULTS SUMMARY")
    print("=" * 70)
    print(f"Spoken turns completed: {spoken_turns} / {list(range(1, 7))}")

    agent.tts.stop()

    if len(spoken_turns) == 6:
        print("[SUCCESS] All 6 turns (including turns 2 to 6) were spoken out loud!")
    else:
        print(f"[FAILURE] Only turns {spoken_turns} were spoken.")
        sys.exit(1)


if __name__ == "__main__":
    run_six_turns()
