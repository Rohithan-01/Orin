"""User confirmation evaluation and management for medium/high risk actions."""

from __future__ import annotations

from orin.config.settings import OrinConfig, get_config
from orin.security.policy import RiskTier


def requires_confirmation(risk_level: RiskTier | str, config: OrinConfig | None = None) -> bool:
    """Determines if the given risk level requires explicit user confirmation.

    LOW: Always False (auto-approved).
    MEDIUM: True if config.security.ask_confirmation_medium is True.
    HIGH: True if config.security.ask_confirmation_high is True (default True).
    """
    cfg = config or get_config()
    tier = RiskTier(risk_level) if isinstance(risk_level, str) else risk_level

    if tier == RiskTier.LOW:
        return False
    elif tier == RiskTier.MEDIUM:
        return cfg.security.ask_confirmation_medium
    elif tier == RiskTier.HIGH:
        return cfg.security.ask_confirmation_high
    return True
