"""Security subsystem: folder allowlist, risk tiers, audit logging, and prompt injection defense."""

from orin.security.audit import AuditLogger, get_audit_logger
from orin.security.confirmation import requires_confirmation
from orin.security.policy import (
    RiskTier,
    is_path_allowlisted,
    sanitize_external_content,
)

__all__ = [
    "RiskTier",
    "is_path_allowlisted",
    "sanitize_external_content",
    "AuditLogger",
    "get_audit_logger",
    "requires_confirmation",
]
