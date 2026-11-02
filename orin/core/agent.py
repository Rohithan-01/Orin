"""Assistant coordinator managing conversation turns, memory integration, voice commands, and hands-free voice loop."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Generator

import numpy as np

from orin.cli.console import (
    console,
    format_status_bar,
    format_voice_state_bar,
    print_banner,
)
from orin.cli.doctor import check_connectivity
from orin.config.settings import OrinConfig, get_config
from orin.core.prompts import build_system_prompt
from orin.core.router import (
    IntentClassifier,
    IntentDispatcher,
    IntentType,
    get_intent_classifier,
    get_intent_dispatcher,
)
from orin.llm.client import OllamaClient, get_llm_client
from orin.memory.store import MemoryStore, get_memory_store
from orin.voice.audio import (
    AudioCapture,
    get_audio_capture,
    get_selected_mic_info,
    is_hotkey_pressed,
    is_terminal_enter_pressed,
)
from orin.voice.stt import WhisperTranscriber, get_transcriber
from orin.voice.tts import (
    SentenceSplitter,
    TTSPlayer,
    get_effective_voice_id,
    get_tts_player,
    handle_voice_command,
)

logger = logging.getLogger(__name__)

EXIT_CONVERSATION_TRIGGERS = (
    "that's all",
    "that is all",
    "thats all",
    "goodbye",
    "bye for now",
    "see you later",
    "exit conversation",
)


class OrinAgent:
    """Core conversational agent coordinating memory, prompts, voice control, and hands-free voice loop."""

    def __init__(
        self,
        config: OrinConfig | None = None,
        llm_client: OllamaClient | None = None,
        memory_store: MemoryStore | None = None,
        tts_player: TTSPlayer | None = None,
        transcriber: WhisperTranscriber | None = None,
        audio_capture: AudioCapture | None = None,
        router_classifier: IntentClassifier | None = None,
        router_dispatcher: IntentDispatcher | None = None,
        session_id: str | None = None,
        speak_by_default: bool = False,
    ) -> None:
        self.config = config or get_config()
        self.llm = llm_client or get_llm_client()
        self.memory = memory_store or get_memory_store()
        self.tts = tts_player or get_tts_player()
        self.transcriber = transcriber or get_transcriber()
        self.audio = audio_capture or get_audio_capture()
        self.router_classifier = router_classifier or get_intent_classifier()
        self.router_dispatcher = router_dispatcher or get_intent_dispatcher()
        self.session_id = session_id or uuid.uuid4().hex[:8]
        self.speak_by_default = speak_by_default

    def build_messages(self, current_user_input: str) -> list[dict[str, str]]:
        """Constructs the LLM message history: system prompt + rolling summary + last 10 turns."""
        prefs = self.memory.get_all_preferences()
        summary = self.memory.get_latest_summary(self.session_id)

        user_name = prefs.get("user_name", self.config.general.user_name)

        system_prompt = build_system_prompt(
            user_name=user_name,
            preferences=prefs,
            memory_summary=summary,
        )

        messages = [{"role": "system", "content": system_prompt}]

        recent_turns = self.memory.get_recent_turns(self.session_id, limit=10)
        for turn in recent_turns:
            messages.append({"role": turn["role"], "content": turn["content"]})

        messages.append({"role": "user", "content": current_user_input})
        return messages

    def handle_turn(
        self, user_input: str, speak: bool | None = None
    ) -> Generator[str]:
        """Processes a user message, streams reply tokens, sends sentences to TTS, and saves to memory."""
        clean_input = user_input.strip()
        if not clean_input:
            return

        should_speak = self.speak_by_default if speak is None else speak
        if should_speak:
            self.tts.interrupt_event.clear()

        # 1. Stop / interrupt trigger
        if clean_input.lower() in ("stop", "cancel", "shut up", "be quiet"):
            self.tts.interrupt()
            yield "Stopped."
            return

        # 2. Check for voice settings commands (e.g. 'speak slower', 'change voice', 'mute voice')
        voice_ack = handle_voice_command(clean_input, self.config)
        if voice_ack:
            self.memory.add_turn(self.session_id, "user", clean_input)
            self.memory.add_turn(self.session_id, "assistant", voice_ack)
            if should_speak and not self.config.voice.muted:
                self.tts.enqueue_sentence(voice_ack)
            yield voice_ack
            return

        # 3. Check for personal preference / identity cues
        pref = self.llm.extract_preference_if_any(clean_input)
        if pref:
            key, val = pref
            self.memory.set_preference(key, val)

        # 4. Check command router for system tools, notes, reminders, files, help
        intent = self.router_classifier.classify(clean_input)
        if intent.intent_type != IntentType.CONVERSATION:
            try:
                dispatch_res = self.router_dispatcher.dispatch(intent)
                if dispatch_res.handled:
                    reply_text = dispatch_res.display_text or dispatch_res.spoken_response
                    self.memory.add_turn(self.session_id, "user", clean_input)
                    self.memory.add_turn(self.session_id, "assistant", reply_text)
                    if should_speak and not self.config.voice.muted:
                        spoken_msg = dispatch_res.spoken_response or dispatch_res.display_text
                        if spoken_msg:
                            self.tts.enqueue_sentence(spoken_msg)
                    yield reply_text
                    return
            except Exception as e:
                err_msg = f"Sorry, I ran into an issue: {e}"
                self.memory.add_turn(self.session_id, "user", clean_input)
                self.memory.add_turn(self.session_id, "assistant", err_msg)
                if should_speak and not self.config.voice.muted:
                    self.tts.enqueue_sentence(err_msg)
                yield err_msg
                return

        # 5. Record user turn in memory
        self.memory.add_turn(self.session_id, "user", clean_input)

        # 6. Build messages with context
        messages = self.build_messages(clean_input)

        # 7. Stream response from LLM sentence-by-sentence into TTS queue
        sentence_splitter = SentenceSplitter()
        collected_tokens: list[str] = []

        try:
            for token in self.llm.stream_chat(messages):
                # Check if interrupted mid-stream
                if self.tts.interrupt_event.is_set():
                    break

                collected_tokens.append(token)
                yield token

                if should_speak and not self.config.voice.muted:
                    new_sentences = sentence_splitter.add_token(token)
                    for sentence in new_sentences:
                        self.tts.enqueue_sentence(sentence)

            # Flush any remaining text in the sentence buffer
            if should_speak and not self.config.voice.muted and not self.tts.interrupt_event.is_set():
                final_sentences = sentence_splitter.flush()
                for sentence in final_sentences:
                    self.tts.enqueue_sentence(sentence)
        except Exception as e:
            err_msg = f"Sorry, I encountered an issue processing that: {e}"
            self.memory.add_turn(self.session_id, "assistant", err_msg)
            if should_speak and not self.config.voice.muted:
                self.tts.enqueue_sentence(err_msg)
            yield err_msg
            return

        full_reply = "".join(collected_tokens).strip()

        # Fallback if model generated no text and was not interrupted
        if not full_reply and not self.tts.interrupt_event.is_set():
            empty_msg = "I'm ready. How can I help you?"
            self.memory.add_turn(self.session_id, "assistant", empty_msg)
            if should_speak and not self.config.voice.muted:
                self.tts.enqueue_sentence(empty_msg)
            yield empty_msg
            return

        # 8. Record assistant reply in memory
        if full_reply:
            self.memory.add_turn(self.session_id, "assistant", full_reply)

        # 9. Compress older turns into rolling summary if needed
        self._maybe_compress_memory()

    def _maybe_compress_memory(self) -> None:
        """Compresses turns older than the last 10 turns into a rolling summary."""
        turn_count = self.memory.get_turn_count(self.session_id)
        if turn_count > 16:
            older_turns = self.memory.get_older_unsummarized_turns(self.session_id, keep_recent=10)
            if older_turns:
                new_summary = self.llm.summarize_conversation(older_turns)
                if new_summary:
                    self.memory.save_summary(
                        self.session_id, new_summary, turns_covered=len(older_turns)
                    )

    def run_text_chat_loop(self, speak: bool = False) -> None:
        """Runs the interactive typed terminal conversation loop."""
        print_banner("Interactive Assistant Chat")

        conn_res = check_connectivity()
        is_online = conn_res.status == "PASS"

        user_name = self.memory.get_preference("user_name", self.config.general.user_name)
        mode = "VOICE" if speak else "TEXT"

        status_bar = format_status_bar(
            online=is_online,
            mode=mode,
            listening=False,
            model=self.config.llm.model,
            user_name=user_name,
        )
        console.print(status_bar)
        console.print()

        greeting = f"Hi {user_name}, Orin is ready."
        console.print(f"[bold cyan]Orin:[/bold cyan] {greeting}\n")

        if speak and not self.config.voice.muted:
            self.tts.enqueue_sentence(greeting)

        console.print("[dim]Type your message and press Enter. Commands: /clear, /status, /exit[/dim]\n")

        while True:
            try:
                user_input = console.input("[bold green]You:[/bold green] ").strip()
            except (KeyboardInterrupt, EOFError):
                self.tts.interrupt()
                console.print("\n[dim]Goodbye![/dim]")
                break

            if not user_input:
                continue

            if user_input.lower() in ("/exit", "/quit", "exit", "quit"):
                self.tts.interrupt()
                console.print("[bold cyan]Orin:[/bold cyan] Goodbye! Have a great day.\n")
                break

            if user_input.lower() == "/clear":
                self.tts.interrupt()
                self.memory.clear_session(self.session_id)
                console.print("[dim]Conversation context cleared.[/dim]\n")
                continue

            if user_input.lower() == "/status":
                turns = self.memory.get_turn_count(self.session_id)
                voice_name = self.config.voice.voice_id.split("\\")[-1] if self.config.voice.voice_id else "Default"
                console.print(
                    f"[dim]Session: {self.session_id} | Turns: {turns} | Rate: {self.config.voice.rate} wpm | Voice: {voice_name}[/dim]\n"
                )
                continue

            console.print("[bold cyan]Orin:[/bold cyan] ", end="")
            try:
                for token in self.handle_turn(user_input, speak=speak):
                    console.print(token, end="")
                console.print("\n")
            except KeyboardInterrupt:
                self.tts.interrupt()
                console.print("\n[dim][Interrupted by user][/dim]\n")

    def run_voice_conversation_loop(self) -> None:
        """Runs the hands-free voice conversation loop with status transitions:

        IDLE -> LISTENING -> THINKING -> SPEAKING -> LISTENING ...
        Terminates on 'that's all', 'exit', or 30 seconds of inactivity.
        """
        print_banner("Voice Assistant (Hands-Free Loop)")

        conn_res = check_connectivity()
        is_online = conn_res.status == "PASS"

        user_name = self.memory.get_preference("user_name", self.config.general.user_name)
        greeting = f"Hi {user_name}, Orin is ready."
        hotkey_name = self.config.voice.hotkey or "F9"
        mic_info = get_selected_mic_info(self.audio.device)

        console.print(
            format_voice_state_bar(
                "IDLE",
                online=is_online,
                model=self.config.llm.model,
                user_name=user_name,
                hotkey=hotkey_name,
            )
        )
        console.print(
            f"[dim]Selected Microphone: [bold cyan]{mic_info['name']}[/bold cyan] (Device #{mic_info['index']}, {mic_info['sample_rate']} Hz)[/dim]"
        )
        console.print(f"\n[bold cyan]Orin:[/bold cyan] {greeting}\n")

        # Initial spoken greeting
        if not self.config.voice.muted:
            self.tts.enqueue_sentence(greeting)

        in_conversation = False
        last_speech_time = time.time()
        trigger_src = ""

        try:
            while True:
                # ----------------------------------------------------
                # STATE: IDLE
                # ----------------------------------------------------
                if not in_conversation:
                    # Poll for activation: Hotkey (F9 / F8 / Ctrl+Space) or Terminal Enter
                    if is_hotkey_pressed(hotkey_name):
                        trigger_src = f"Hotkey [{hotkey_name}]"
                        console.print(
                            f"\n[bold yellow][STAGE 1/5: HOTKEY DETECTED][/bold yellow] Triggered via: [bold cyan]{trigger_src}[/bold cyan] -> Starting voice interaction"
                        )
                        in_conversation = True
                        last_speech_time = time.time()
                    elif is_terminal_enter_pressed():
                        trigger_src = "Terminal ENTER key"
                        console.print(
                            f"\n[bold yellow][STAGE 1/5: HOTKEY DETECTED][/bold yellow] Triggered via: [bold cyan]{trigger_src}[/bold cyan] (terminal fallback) -> Starting voice interaction"
                        )
                        in_conversation = True
                        last_speech_time = time.time()
                    elif self.config.voice.wake_word_enabled:
                        # Lightweight energy check
                        quick_frame = self.audio.record_until_silence(silence_timeout=0.8, max_duration=2.5)
                        if len(quick_frame) > 0:
                            detected_text = self.transcriber.transcribe(quick_frame).lower()
                            if "orin" in detected_text or "hey orin" in detected_text:
                                trigger_src = "Wake word ('Hey Orin')"
                                console.print(
                                    f"\n[bold yellow][STAGE 1/5: HOTKEY DETECTED][/bold yellow] Triggered via: [bold cyan]{trigger_src}[/bold cyan]"
                                )
                                in_conversation = True
                                last_speech_time = time.time()
                                self.tts.enqueue_sentence("I'm listening.")
                                time.sleep(0.5)

                    if not in_conversation:
                        time.sleep(0.04)
                        continue

                # ----------------------------------------------------
                # STATE: LISTENING
                # ----------------------------------------------------
                console.print(
                    format_voice_state_bar(
                        "LISTENING",
                        online=is_online,
                        model=self.config.llm.model,
                        user_name=user_name,
                        hotkey=hotkey_name,
                    )
                )

                # Check 60 seconds timeout of silence in active conversation
                if time.time() - last_speech_time > 60.0:
                    timeout_msg = f"Going back to idle after 60 seconds of silence. Press {hotkey_name} or ENTER whenever you need me."
                    console.print(f"\n[dim]{timeout_msg}[/dim]\n")
                    if not self.config.voice.muted:
                        logger.info("speaking started")
                        console.print("[bold yellow][STAGE: SPEAKING STARTED][/bold yellow]")
                        self.tts.enqueue_sentence("Going back to idle. Talk to you soon.")
                        while self.tts.is_speaking():
                            time.sleep(0.04)
                        logger.info("speaking finished")
                        console.print("[bold yellow][STAGE: SPEAKING FINISHED][/bold yellow]\n")
                    in_conversation = False
                    trigger_src = ""
                    console.print(
                        format_voice_state_bar(
                            "IDLE",
                            online=is_online,
                            model=self.config.llm.model,
                            user_name=user_name,
                            hotkey=hotkey_name,
                        )
                    )
                    continue

                # Log listening start
                logger.info("listening started")
                console.print(
                    f"[bold yellow][STAGE: LISTENING STARTED][/bold yellow] Listening on mic '[bold cyan]{mic_info['name']}[/bold cyan]' (Hold {hotkey_name} or speak naturally)..."
                )

                # Record audio from microphone
                if trigger_src or is_hotkey_pressed(hotkey_name) or is_terminal_enter_pressed():
                    audio_data = self.audio.record_push_to_talk(max_duration=20.0, hotkey_str=hotkey_name)
                else:
                    audio_data = self.audio.record_until_silence(silence_timeout=1.2, max_duration=20.0)

                trigger_src = ""  # Reset single-shot trigger flag

                # Log recording stopped
                dur = len(audio_data) / 16000.0 if len(audio_data) > 0 else 0.0
                amp = float(np.max(np.abs(audio_data))) if len(audio_data) > 0 else 0.0
                console.print(
                    f"[dim][STAGE: RECORDING STOPPED][/dim] Captured {dur:.2f}s ({len(audio_data)} samples, peak amplitude: {amp:.4f})"
                )

                # ----------------------------------------------------
                # STATE: THINKING
                # ----------------------------------------------------
                console.print(
                    format_voice_state_bar(
                        "THINKING",
                        online=is_online,
                        model=self.config.llm.model,
                        user_name=user_name,
                        hotkey=hotkey_name,
                    )
                )

                user_text = self.transcriber.transcribe(audio_data)

                if not user_text:
                    console.print(
                        f"[dim][STAGE: TRANSCRIPT TEXT][/dim] [No clear speech recognized / sound level {amp:.4f} below threshold]"
                    )
                    time.sleep(0.1)
                    continue

                # Speech recognized! Reset 60s inactivity timer
                last_speech_time = time.time()
                console.print(
                    f"[bold yellow][STAGE: TRANSCRIPT TEXT][/bold yellow] '[bold green]{user_text}[/bold green]'"
                )
                console.print(f"[bold green]You (voice):[/bold green] {user_text}")

                # Check exit triggers (e.g. "that's all", "goodbye")
                clean_lower = user_text.lower().strip(" .!?,")
                if any(exit_cmd in clean_lower for exit_cmd in EXIT_CONVERSATION_TRIGGERS):
                    goodbye_msg = "Alright, talk to you later!"
                    console.print(f"[bold cyan]Orin:[/bold cyan] {goodbye_msg}\n")
                    if not self.config.voice.muted:
                        logger.info("speaking started")
                        console.print("[bold yellow][STAGE: SPEAKING STARTED][/bold yellow]")
                        self.tts.enqueue_sentence(goodbye_msg)
                        while self.tts.is_speaking():
                            time.sleep(0.04)
                        logger.info("speaking finished")
                        console.print("[bold yellow][STAGE: SPEAKING FINISHED][/bold yellow]\n")
                    in_conversation = False
                    console.print(
                        format_voice_state_bar(
                            "IDLE",
                            online=is_online,
                            model=self.config.llm.model,
                            user_name=user_name,
                            hotkey=hotkey_name,
                        )
                    )
                    continue

                if clean_lower in ("stop", "cancel"):
                    self.tts.interrupt()
                    console.print("[dim]Action stopped.[/dim]\n")
                    continue

                # ----------------------------------------------------
                # STATE: SPEAKING
                # ----------------------------------------------------
                console.print(
                    format_voice_state_bar(
                        "SPEAKING",
                        online=is_online,
                        model=self.config.llm.model,
                        user_name=user_name,
                        hotkey=hotkey_name,
                    )
                )

                voice_id, voice_name = get_effective_voice_id(self.config)
                voice_desc = voice_name or (self.config.voice.voice_id.split("\\")[-1] if self.config.voice.voice_id else "Microsoft Zira Desktop")
                logger.info("speaking started")
                console.print(
                    f"[bold yellow][STAGE: SPEAKING STARTED][/bold yellow] Engine: {self.config.voice.engine}, Voice: '{voice_desc}', Rate: {self.config.voice.rate} wpm"
                )
                console.print("[bold cyan]Orin:[/bold cyan] ", end="")

                collected_reply: list[str] = []
                try:
                    for token in self.handle_turn(user_text, speak=True):
                        console.print(token, end="")
                        collected_reply.append(token)
                        # Allow immediate interruption with Hotkey or Enter
                        if is_hotkey_pressed(hotkey_name) or is_terminal_enter_pressed():
                            self.tts.interrupt()
                            console.print(f"\n[dim][Interrupted by {hotkey_name}/Enter][/dim]")
                            break
                    console.print("\n")
                except KeyboardInterrupt:
                    self.tts.interrupt()
                    console.print("\n[dim][Interrupted by user][/dim]\n")

                full_reply = "".join(collected_reply).strip()
                if full_reply:
                    console.print(f"[dim][STAGE: REPLY TEXT][/dim] '{full_reply}'\n")

                # Wait for current sentences to finish speaking before re-opening mic
                while self.tts.is_speaking():
                    if is_hotkey_pressed(hotkey_name) or is_terminal_enter_pressed():
                        self.tts.interrupt()
                        break
                    time.sleep(0.04)

                logger.info("speaking finished")
                console.print("[bold yellow][STAGE: SPEAKING FINISHED][/bold yellow]\n")

                # Reset timer so user has 60s to respond hands-free
                last_speech_time = time.time()
                # Automatically loops back to LISTENING!

        except KeyboardInterrupt:
            self.tts.interrupt()
            console.print("\n[dim]Orin voice loop exited.[/dim]\n")
