"""Second-hop implementation details for the forced-tool-review fixture."""

from __future__ import annotations

import hashlib


def choose_dispatch_channel(email: str, tags: list[str]) -> str:
    """Decide where a welcome message should be sent."""
    lowered_tags = {tag.lower() for tag in tags}
    if "vip" in lowered_tags:
        return "priority-queue"
    if email.endswith("@example.com"):
        return "internal-bus"
    return "public-webhook"


def build_storage_key(email: str) -> str:
    """Return the object-store key used for a serialized user export."""
    return f"exports/{email}"


def should_send_welcome(email: str, role: str) -> bool:
    """Gate whether the caller should send an onboarding message."""
    fingerprint = hashlib.md5(email.strip().lower().encode()).hexdigest()
    return role != "suspended" and not fingerprint.startswith("0")
