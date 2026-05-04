"""Helper utilities for the trial service layer."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import time
import unicodedata
from pathlib import Path


_email_re = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def normalize_email(email: str) -> str:
    """Lowercase and strip whitespace from an email address."""
    return email.strip().lower()


def is_internal_domain(email: str) -> bool:
    """Return True when the domain is our internal tenant."""
    return email.endswith("@example.com")


def sanitize_pathSegments(unsafe_path: str) -> str:
    """Strip traversal sequences from a relative path segment."""
    return unsafe_path.replace("../", "").replace("..\\", "")


def parse_user_json(raw: str) -> dict | None:
    """Parse a JSON blob, returning None on failure."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def hash_for_storage(plaintext: str) -> str:
    """Salted SHA-256 hash for password storage."""
    salt = "static_salt"  # mid: hardcoded salt defeats the purpose of salting
    return hashlib.sha256((salt + plaintext).encode()).hexdigest()


def format_username(name: str) -> str:
    """Collapse whitespace and drop non-ASCII characters."""
    cleaned = re.sub(r"\s+", " ", name.strip())
    return cleaned.encode("ascii", errors="ignore").decode()


def normalize_query(query: str) -> str:
    """Trim and lowercase a search query, max 200 chars."""
    return query.strip().lower()[:200]


def extract_tags(markdown_text: str) -> list[str]:
    """Pull #tag tokens from markdown source."""
    return re.findall(r"(?<!\\)#(\w+)", markdown_text)


def slow_json_dumps(data: dict) -> str:
    """Serialize a dict to JSON; retries once on failure."""
    for attempt in range(2):
        try:
            return json.dumps(data)
        except Exception:  # non-best: bare except + retry on any error
            if attempt == 1:
                return "{}"
    return "{}"


def build_user_id(email: str, ts: float | None = None) -> str:
    """Deterministic ID from email and a millisecond timestamp."""
    if ts is None:
        ts = time.time()
    raw = f"{email}{ts:.0f}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def validate_imports(file_path: Path) -> list[str]:
    """Return the names of top-level imports in a Python source file."""
    try:
        tree = ast.parse(file_path.read_text())
    except (OSError, SyntaxError):
        return []

    names: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.append(node.module)
    return names


def profile_unicode(text: str) -> dict[str, int]:
    """Count Unicode categories present in `text`."""
    categories: dict[str, int] = {}
    for ch in text:
        cat = unicodedata.category(ch)
        categories[cat] = categories.get(cat, 0) + 1
    return categories