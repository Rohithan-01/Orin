"""Audit logging for all assistant actions, risk levels, and confirmations."""

from __future__ import annotations

from typing import Any

from orin.memory.db import get_db, init_db
from orin.security.policy import RiskTier


class AuditLogger:
    """Manages an append-only audit trail in the local SQLite database."""

    def __init__(self) -> None:
        init_db()

    def log(
        self,
        action: str,
        risk_level: RiskTier | str,
        details: str = "",
        confirmed: bool = True,
    ) -> int:
        """Records an action into the audit_log table. Returns the new log ID."""
        init_db()
        level_str = risk_level.value if isinstance(risk_level, RiskTier) else str(risk_level)
        with get_db() as conn:
            cur = conn.execute(
                """
                INSERT INTO audit_log (action, risk_level, details, confirmed)
                VALUES (?, ?, ?, ?);
                """,
                (action, level_str, details, 1 if confirmed else 0),
            )
            return cur.lastrowid or 0

    def get_recent_logs(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieves recent audit log entries in reverse chronological order."""
        init_db()
        with get_db() as conn:
            cur = conn.execute(
                """
                SELECT id, action, risk_level, details, confirmed, timestamp
                FROM audit_log
                ORDER BY id DESC
                LIMIT ?;
                """,
                (limit,),
            )
            rows = cur.fetchall()
            return [
                {
                    "id": r["id"],
                    "action": r["action"],
                    "risk_level": r["risk_level"],
                    "details": r["details"] or "",
                    "confirmed": bool(r["confirmed"]),
                    "timestamp": str(r["timestamp"]),
                }
                for r in rows
            ]

    def count_by_risk(self) -> dict[str, int]:
        """Summarizes action counts grouped by risk level."""
        init_db()
        with get_db() as conn:
            cur = conn.execute("SELECT risk_level, COUNT(*) as cnt FROM audit_log GROUP BY risk_level;")
            rows = cur.fetchall()
            return {r["risk_level"]: r["cnt"] for r in rows}


_global_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    """Singleton getter for AuditLogger."""
    global _global_audit_logger
    if _global_audit_logger is None:
        _global_audit_logger = AuditLogger()
    return _global_audit_logger
