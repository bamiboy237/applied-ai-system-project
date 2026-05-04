"""Visible wrapper layer for the forced-tool-review fixture."""

from trial.hidden_rules import (
    build_storage_key,
    choose_dispatch_channel,
    should_send_welcome,
)


def select_dispatch_channel(email: str, tags: list[str]) -> str:
    """Pick the dispatch channel for a user-facing notification."""
    return choose_dispatch_channel(email, tags)


def make_storage_key(email: str) -> str:
    """Build the storage key used for an exported user payload."""
    return build_storage_key(email)


def can_send_welcome(email: str, role: str) -> bool:
    """Return whether the caller should send a welcome notification."""
    return should_send_welcome(email, role)
