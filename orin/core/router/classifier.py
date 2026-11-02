"""Fast intent classification engine using deterministic rules with zero latency."""

from __future__ import annotations

import re

from orin.core.router.intents import IntentType, ParsedIntent


class IntentClassifier:
    """Classifies user queries into discrete executable intents."""

    def classify(self, query: str) -> ParsedIntent:
        """Evaluates query against pattern matchers and returns a ParsedIntent."""
        clean = query.strip()
        lower = clean.lower()

        # 1. System stats / Hardware monitoring
        if any(w in lower for w in ("battery level", "battery status", "how much battery", "check battery", "power status")):
            return ParsedIntent(
                intent_type=IntentType.SYSTEM_STATS,
                parameters={"target": "battery"},
                raw_query=clean,
            )
        if any(w in lower for w in ("system stats", "system status", "cpu usage", "ram usage", "memory usage", "system health", "how is my cpu", "how's my cpu")):
            return ParsedIntent(
                intent_type=IntentType.SYSTEM_STATS,
                parameters={"target": "all"},
                raw_query=clean,
            )

        # 2. Volume control
        if lower in ("mute", "mute sound", "mute audio", "mute volume", "silence audio"):
            return ParsedIntent(
                intent_type=IntentType.VOLUME_CONTROL,
                parameters={"action": "mute"},
                raw_query=clean,
            )
        vol_match = re.search(r"\b(?:set\s+volume\s+to|volume\s+to)\s+(\d{1,3})\b", lower)
        if vol_match:
            level = int(vol_match.group(1))
            return ParsedIntent(
                intent_type=IntentType.VOLUME_CONTROL,
                parameters={"action": "set", "level": level},
                raw_query=clean,
            )

        # 3. Application launching
        app_match = re.match(
            r"^(?:open|launch|start|run)\s+(?:the\s+)?([a-z0-9_\-\s]+?)(?:\s+app|\s+program|\s+application)?$",
            lower,
        )
        if app_match:
            app_target = app_match.group(1).strip()
            first_word = app_target.split()[0] if app_target.split() else ""
            # Exclude false positives like "open file" or "open note"
            if first_word not in ("file", "document", "note", "notes", "folder", "reminder"):
                return ParsedIntent(
                    intent_type=IntentType.APP_LAUNCH,
                    parameters={"app_name": app_target},
                    raw_query=clean,
                )

        # 4. Notes creation
        note_create_match = re.match(
            r"^(?:take\s+a\s+note(?:\s+that|\s*:)?|create\s+a\s+note(?:\s+that|\s*:)?|write\s+a\s+note(?:\s*:)?|note\s*:)\s*(.+)$",
            clean,
            flags=re.IGNORECASE,
        )
        if note_create_match:
            return ParsedIntent(
                intent_type=IntentType.NOTE_CREATE,
                parameters={"content": note_create_match.group(1).strip()},
                raw_query=clean,
            )

        # 5. Notes retrieval / searching
        if any(w in lower for w in ("show my notes", "list notes", "show notes", "what are my notes", "read my notes", "get notes")):
            return ParsedIntent(
                intent_type=IntentType.NOTE_LIST,
                parameters={"query": ""},
                raw_query=clean,
            )
        note_search_match = re.search(r"\b(?:search\s+notes\s+for|find\s+note\s+about)\s+(.+)$", lower)
        if note_search_match:
            return ParsedIntent(
                intent_type=IntentType.NOTE_LIST,
                parameters={"query": note_search_match.group(1).strip()},
                raw_query=clean,
            )

        # 6. Reminders creation
        rem_create_match = re.match(
            r"^(?:remind\s+me\s+to|set\s+a\s+reminder\s+to|create\s+a\s+reminder\s+to)\s+(.+)$",
            clean,
            flags=re.IGNORECASE,
        )
        if rem_create_match:
            return ParsedIntent(
                intent_type=IntentType.REMINDER_CREATE,
                parameters={"message": rem_create_match.group(1).strip()},
                raw_query=clean,
            )

        # 7. Reminders retrieval
        if any(w in lower for w in ("show reminders", "list reminders", "what are my reminders", "show my reminders", "pending reminders")):
            return ParsedIntent(
                intent_type=IntentType.REMINDER_LIST,
                parameters={},
                raw_query=clean,
            )

        # 8. File search
        file_search_match = re.search(
            r"\b(?:search\s+files\s+for|search\s+for\s+file|find\s+file|find\s+files|search\s+documents\s+for)\s+([^\n\r]+)$",
            lower,
        )
        if file_search_match:
            target = file_search_match.group(1).strip()
            return ParsedIntent(
                intent_type=IntentType.FILE_SEARCH,
                parameters={"query": target},
                raw_query=clean,
            )

        # 9. File read
        file_read_match = re.search(
            r"\b(?:read\s+file|view\s+file|read\s+content\s+of|show\s+file)\s+([^\n\r]+)$",
            lower,
        )
        if file_read_match:
            target_path = file_read_match.group(1).strip().strip("\"'")
            return ParsedIntent(
                intent_type=IntentType.FILE_READ,
                parameters={"path": target_path},
                raw_query=clean,
            )

        # 10. Weather inquiry
        weather_match = re.search(
            r"\b(?:what(?:'s|\s+is|\s+about)?\s+(?:the\s+)?weather\s+(?:in|for|at)\s+([a-zA-Z\s,]+)|weather\s+(?:forecast\s+)?(?:in|for|at)\s+([a-zA-Z\s,]+)|weather\s+in\s+([a-zA-Z\s,]+)|temperature\s+in\s+([a-zA-Z\s,]+))\b",
            lower,
        )
        if weather_match:
            loc = next(g for g in weather_match.groups() if g is not None).strip()
            return ParsedIntent(
                intent_type=IntentType.WEATHER,
                parameters={"location": loc},
                raw_query=clean,
            )
        if any(w in lower for w in ("what's the weather", "what is the weather", "how's the weather", "check weather", "weather forecast", "current weather")):
            return ParsedIntent(
                intent_type=IntentType.WEATHER,
                parameters={"location": ""},
                raw_query=clean,
            )

        # 11. Web search / online lookups
        search_match = re.match(
            r"^(?:search\s+(?:the\s+)?web\s+for|search\s+online\s+for|look\s+up\s+online|look\s+up|google)\s+(.+)$",
            lower,
        )
        if search_match:
            search_query = search_match.group(1).strip()
            return ParsedIntent(
                intent_type=IntentType.WEB_SEARCH,
                parameters={"query": search_query},
                raw_query=clean,
            )

        # 12. Help and capabilities
        if any(
            w in lower
            for w in (
                "what can you do",
                "what can i say",
                "what are your commands",
                "show commands",
                "list commands",
                "what do you do",
                "tell me what you can do",
                "help me",
            )
        ) or lower in ("help", "commands"):
            return ParsedIntent(
                intent_type=IntentType.HELP,
                raw_query=clean,
            )

        # 13. Default: pure conversational or general AI turn
        return ParsedIntent(
            intent_type=IntentType.CONVERSATION,
            confidence=0.5,
            raw_query=clean,
        )


_global_classifier: IntentClassifier | None = None


def get_intent_classifier() -> IntentClassifier:
    """Singleton getter for IntentClassifier."""
    global _global_classifier
    if _global_classifier is None:
        _global_classifier = IntentClassifier()
    return _global_classifier
