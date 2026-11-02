"""Intent dispatcher executing tools under security policy and logging to audit trail."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from orin.config.settings import OrinConfig, get_config
from orin.core.router.intents import IntentType, ParsedIntent
from orin.net.search import search_web
from orin.net.weather import get_weather
from orin.security.audit import get_audit_logger
from orin.security.confirmation import requires_confirmation
from orin.security.policy import RiskTier
from orin.tools.files import read_file_safe, search_files
from orin.tools.indexer import get_file_indexer
from orin.tools.notes import create_note, get_notes, search_notes
from orin.tools.reminders import create_reminder, get_pending_reminders
from orin.tools.system import (
    format_system_summary,
    get_battery_status,
    launch_app,
    mute_system_volume,
    set_system_volume,
)


@dataclass
class DispatchResult:
    """Outcome of an intent dispatch execution."""

    handled: bool
    spoken_response: str
    display_text: str = ""
    risk_tier: RiskTier = RiskTier.LOW
    action_name: str = ""
    data: Any = None


class IntentDispatcher:
    """Dispatches intents to tools with security validation and audit logging."""

    def __init__(self, config: OrinConfig | None = None) -> None:
        self.config = config or get_config()
        self.audit = get_audit_logger()
        self.indexer = get_file_indexer()

    def dispatch(self, intent: ParsedIntent) -> DispatchResult:
        """Executes the tool associated with the intent if security checks pass."""
        if intent.intent_type == IntentType.CONVERSATION:
            return DispatchResult(handled=False, spoken_response="")

        risk = intent.risk_tier
        action = intent.intent_type.value

        # Check confirmation requirement
        if requires_confirmation(risk, self.config):
            prompt = f"Confirmation required for action '{action}'. Proceed?"
            return DispatchResult(
                handled=True,
                spoken_response=prompt,
                display_text=prompt,
                risk_tier=risk,
                action_name=action,
            )

        result: DispatchResult

        # 1. System stats
        if intent.intent_type == IntentType.SYSTEM_STATS:
            target = intent.parameters.get("target", "all")
            if target == "battery":
                bat = get_battery_status()
                text = f"Your battery is at {bat['percent']}% and {'charging' if bat['plugged'] else 'running on battery'}."
                result = DispatchResult(handled=True, spoken_response=text, display_text=text, data=bat)
            else:
                summary = format_system_summary()
                result = DispatchResult(handled=True, spoken_response=summary, display_text=summary)

        # 2. Volume control
        elif intent.intent_type == IntentType.VOLUME_CONTROL:
            act = intent.parameters.get("action", "mute")
            if act == "mute":
                msg = mute_system_volume()
                result = DispatchResult(handled=True, spoken_response=msg, display_text=msg)
            else:
                lvl = intent.parameters.get("level", 50)
                msg = set_system_volume(lvl)
                result = DispatchResult(handled=True, spoken_response=msg, display_text=msg)

        # 3. Application launcher
        elif intent.intent_type == IntentType.APP_LAUNCH:
            target_app = intent.parameters.get("app_name", "")
            success, msg = launch_app(target_app)
            result = DispatchResult(
                handled=True,
                spoken_response=msg,
                display_text=msg,
                risk_tier=RiskTier.MEDIUM,
                action_name=f"LAUNCH_{target_app}",
            )

        # 4. Notes creation
        elif intent.intent_type == IntentType.NOTE_CREATE:
            content = intent.parameters.get("content", "")
            note_data = create_note(content=content)
            ack = f"I saved that note: '{note_data['title']}'."
            result = DispatchResult(
                handled=True,
                spoken_response=ack,
                display_text=f"Note Created:\nTitle: {note_data['title']}\nContent: {note_data['content']}",
                data=note_data,
            )

        # 5. Notes retrieval
        elif intent.intent_type == IntentType.NOTE_LIST:
            query = intent.parameters.get("query", "")
            notes = search_notes(query) if query else get_notes(limit=5)
            if not notes:
                msg = "You have no notes matching that." if query else "You don't have any saved notes yet."
                result = DispatchResult(handled=True, spoken_response=msg, display_text=msg)
            else:
                titles = ", ".join(f"'{n['title']}'" for n in notes[:3])
                spoken = f"Found {len(notes)} note{'s' if len(notes) > 1 else ''}: {titles}."
                lines = [f"• [{n['id']}] {n['title']}: {n['content']}" for n in notes]
                display = "Your Notes:\n" + "\n".join(lines)
                result = DispatchResult(handled=True, spoken_response=spoken, display_text=display, data=notes)

        # 6. Reminders creation
        elif intent.intent_type == IntentType.REMINDER_CREATE:
            message = intent.parameters.get("message", "")
            rem_data = create_reminder(message=message)
            ack = f"Reminder set: '{message}'."
            result = DispatchResult(
                handled=True,
                spoken_response=ack,
                display_text=f"Reminder Saved (ID: {rem_data['id']}): {message} at {rem_data['remind_at']}",
                data=rem_data,
            )

        # 7. Reminders retrieval
        elif intent.intent_type == IntentType.REMINDER_LIST:
            rems = get_pending_reminders(limit=5)
            if not rems:
                msg = "You have no pending reminders."
                result = DispatchResult(handled=True, spoken_response=msg, display_text=msg)
            else:
                spoken = f"You have {len(rems)} pending reminder{'s' if len(rems) > 1 else ''}."
                lines = [f"• [{r['id']}] {r['message']} (Due: {r['remind_at']})" for r in rems]
                result = DispatchResult(
                    handled=True,
                    spoken_response=spoken,
                    display_text="Pending Reminders:\n" + "\n".join(lines),
                    data=rems,
                )

        # 8. File search
        elif intent.intent_type == IntentType.FILE_SEARCH:
            q = intent.parameters.get("query", "")
            # Try indexer first, fallback to folder crawl
            indexed_hits = self.indexer.search(q, limit=5)
            if indexed_hits:
                names = ", ".join(h["filename"] for h in indexed_hits[:3])
                spoken = f"Found {len(indexed_hits)} matching file{'s' if len(indexed_hits) > 1 else ''}: {names}."
                lines = [f"• {h['filename']} ({h['path']})" for h in indexed_hits]
                result = DispatchResult(
                    handled=True,
                    spoken_response=spoken,
                    display_text="Matching Files:\n" + "\n".join(lines),
                    data=indexed_hits,
                )
            else:
                raw_hits = search_files(q, config=self.config, limit=5)
                if raw_hits:
                    spoken = f"Found {len(raw_hits)} file{'s' if len(raw_hits) > 1 else ''}."
                    result = DispatchResult(
                        handled=True,
                        spoken_response=spoken,
                        display_text="Matching Files:\n" + "\n".join(f"• {p}" for p in raw_hits),
                        data=raw_hits,
                    )
                else:
                    msg = f"I didn't find any files matching '{q}' in your allowlisted folders."
                    result = DispatchResult(handled=True, spoken_response=msg, display_text=msg)

        # 9. File read
        elif intent.intent_type == IntentType.FILE_READ:
            target_path = intent.parameters.get("path", "")
            success, content = read_file_safe(target_path, config=self.config)
            if success:
                spoken = f"Here is the content of {target_path}."
                result = DispatchResult(
                    handled=True,
                    spoken_response=spoken,
                    display_text=content,
                    action_name=f"READ_{target_path}",
                )
            else:
                result = DispatchResult(
                    handled=True,
                    spoken_response=content,
                    display_text=content,
                    action_name=f"READ_FAIL_{target_path}",
                )

        # 10. Weather inquiry
        elif intent.intent_type == IntentType.WEATHER:
            loc = intent.parameters.get("location", "")
            w_res = get_weather(location=loc, config=self.config)
            spoken = w_res.get("spoken", "Could not retrieve weather information.")
            result = DispatchResult(
                handled=True,
                spoken_response=spoken,
                display_text=spoken,
                data=w_res,
            )

        # 11. Web search
        elif intent.intent_type == IntentType.WEB_SEARCH:
            q = intent.parameters.get("query", "")
            s_res = search_web(query=q)
            spoken = s_res.get("spoken", "Web search completed.")
            display = s_res.get("snippet") or spoken
            result = DispatchResult(
                handled=True,
                spoken_response=spoken,
                display_text=display,
                data=s_res,
            )

        # 12. Help and capabilities
        elif intent.intent_type == IntentType.HELP:
            spoken = (
                "I can check your battery and hardware stats, check current weather, search the web, "
                "adjust master volume, launch applications like Notepad and Calculator, create and search notes, "
                "set reminders, search allowlisted files, and answer general questions. "
                "What would you like me to do?"
            )
            display = (
                "Orin Capabilities & Voice Commands:\n"
                "• Hardware: 'What's my battery level?', 'Check CPU and memory'\n"
                "• Weather: 'What's the weather in London?', 'Check weather'\n"
                "• Online Search: 'Search the web for Python 3.13', 'Look up quantum computing online'\n"
                "• Audio: 'Set volume to 70', 'Mute audio'\n"
                "• Apps: 'Open Notepad', 'Launch Calculator', 'Open VS Code'\n"
                "• Notes: 'Take a note: ...', 'Show my notes', 'Search notes for ...'\n"
                "• Reminders: 'Remind me to ... at 5pm', 'Show my reminders'\n"
                "• Files: 'Search files for ...', 'Read file ...'\n"
                "• Conversation: General questions, coding help, and explanations\n"
                "• Exit: Say 'that's all' or pause for 60 seconds."
            )
            result = DispatchResult(handled=True, spoken_response=spoken, display_text=display)

        else:
            result = DispatchResult(handled=False, spoken_response="")

        # Record action in audit log
        self.audit.log(
            action=action,
            risk_level=risk,
            details=intent.raw_query[:200],
            confirmed=True,
        )

        return result


_global_dispatcher: IntentDispatcher | None = None


def get_intent_dispatcher() -> IntentDispatcher:
    """Singleton getter for IntentDispatcher."""
    global _global_dispatcher
    if _global_dispatcher is None:
        _global_dispatcher = IntentDispatcher()
    return _global_dispatcher
