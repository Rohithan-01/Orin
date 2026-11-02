"""Intent definitions and data structures for Orin's intent router."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from orin.security.policy import RiskTier


class IntentType(StrEnum):
    """Categorized intent types supported by Orin."""

    SYSTEM_STATS = "SYSTEM_STATS"
    VOLUME_CONTROL = "VOLUME_CONTROL"
    APP_LAUNCH = "APP_LAUNCH"
    NOTE_CREATE = "NOTE_CREATE"
    NOTE_LIST = "NOTE_LIST"
    REMINDER_CREATE = "REMINDER_CREATE"
    REMINDER_LIST = "REMINDER_LIST"
    FILE_SEARCH = "FILE_SEARCH"
    FILE_READ = "FILE_READ"
    WEATHER = "WEATHER"
    WEB_SEARCH = "WEB_SEARCH"
    HELP = "HELP"
    CONVERSATION = "CONVERSATION"


# Risk tier mapping for each intent type
INTENT_RISK_MAP: dict[IntentType, RiskTier] = {
    IntentType.SYSTEM_STATS: RiskTier.LOW,
    IntentType.VOLUME_CONTROL: RiskTier.MEDIUM,
    IntentType.APP_LAUNCH: RiskTier.MEDIUM,
    IntentType.NOTE_CREATE: RiskTier.MEDIUM,
    IntentType.NOTE_LIST: RiskTier.LOW,
    IntentType.REMINDER_CREATE: RiskTier.MEDIUM,
    IntentType.REMINDER_LIST: RiskTier.LOW,
    IntentType.FILE_SEARCH: RiskTier.LOW,
    IntentType.FILE_READ: RiskTier.LOW,
    IntentType.WEATHER: RiskTier.LOW,
    IntentType.WEB_SEARCH: RiskTier.LOW,
    IntentType.HELP: RiskTier.LOW,
    IntentType.CONVERSATION: RiskTier.LOW,
}


@dataclass
class ParsedIntent:
    """Represents a classified intent with extracted parameters."""

    intent_type: IntentType
    confidence: float = 1.0
    parameters: dict[str, Any] = field(default_factory=dict)
    raw_query: str = ""

    @property
    def risk_tier(self) -> RiskTier:
        return INTENT_RISK_MAP.get(self.intent_type, RiskTier.LOW)
