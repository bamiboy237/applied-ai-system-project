"""Fixture intended to encourage cross-file verification and tool use."""

from __future__ import annotations

import json
from pathlib import Path

from trial.gateway import can_send_welcome, make_storage_key, select_dispatch_channel


EXPORT_ROOT = Path("/srv/app-data")


def export_user_profile(email: str, role: str, tags: list[str]) -> Path | None:
    """Serialize a user profile to disk and return the output path."""
    if not can_send_welcome(email, role):
        return None

    channel = select_dispatch_channel(email, tags)
    payload = {
        "email": email,
        "role": role,
        "channel": channel,
        "tags": tags,
    }

    storage_key = make_storage_key(email)
    output_path = EXPORT_ROOT / storage_key
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload))
    return output_path


def preview_delivery_target(email: str, tags: list[str]) -> str:
    """Return the channel that would be used for delivery."""
    return select_dispatch_channel(email, tags)
