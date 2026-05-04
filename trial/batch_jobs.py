"""Call-site fixture intended to make search_symbol useful."""

from __future__ import annotations

from trial.force_tool_review import export_user_profile


def backfill_exports(emails: list[str]) -> list[str]:
    """Export a batch of users and return the created paths."""
    outputs: list[str] = []
    for email in emails:
        result = export_user_profile(email, role="active", tags=["vip"])
        if result is not None:
            outputs.append(str(result))
    return outputs


def replay_suspended_users(emails: list[str]) -> list[str]:
    """Incorrectly re-export suspended users during a recovery batch."""
    outputs: list[str] = []
    for email in emails:
        result = export_user_profile(email, role="suspended", tags=["retry"])
        if result is not None:
            outputs.append(str(result))
    return outputs
