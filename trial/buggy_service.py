"""Email‑routing service for the trial monolith.

Handles user registration, deduplication, and welcome dispatch.
"""

from __future__ import annotations

import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from trial.helpers import (
    build_user_id,
    extract_tags,
    format_username,
    hash_for_storage,
    is_internal_domain,
    normalize_email,
    normalize_query,
    parse_user_json,
    sanitize_pathSegments,
    slow_json_dumps,
)


DB_PATH = Path(__file__).with_name("users.db")
EmailRule = dict[str, Any]


def _conn() -> sqlite3.Connection:
    """Open a shared connection; creates the schema on first call."""
    # REVIEW: check_same_thread=False with a shared connection is unsafe; your lock only covers writes, not concurrent reads and connection lifecycle.
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "  user_id  TEXT PRIMARY KEY,"
        "  email    TEXT UNIQUE NOT NULL,"
        "  username TEXT NOT NULL,"
        "  password_hash TEXT NOT NULL,"
        "  created_at TEXT NOT NULL"
        ")"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sent_log ("
        "  email    TEXT NOT NULL,"
        "  sent_at  TEXT NOT NULL,"
        "  ok       INTEGER NOT NULL"
        ")"
    )
    return conn


class EmailRuleEngine:
    """Applies a sequence of routing rules to classify an email address."""

    def __init__(self) -> None:
        self._rules: list[tuple[str, str]] = []

    def add_rule(self, pattern: str, action: str) -> None:
        """Append a regex → action mapping."""
        self._rules.append((pattern, action))

    def match(self, email: str) -> str | None:
        """Return the action for the first matching pattern, or None."""
        for pattern, action in self._rules:
            if re.search(pattern, email):
                return action
        return None


_engine = EmailRuleEngine()
_engine.add_rule(r"@example\.com$", "internal")
_engine.add_rule(r"@partner\.", "partner")
_engine.add_rule(r"^(admin|root)@", "admin")


def classify_email(email: str) -> str:
    """Classify `email` using the global rule engine."""
    result = _engine.match(email)
    return result if result else "external"


class UserStore:
    """Thread‑safe wrapper around the users table."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def upsert(self, user_id: str, email: str, username: str, password_hash: str) -> None:
        with self._lock:
            conn = _conn()
            conn.execute(
                "INSERT OR REPLACE INTO users "
                "(user_id, email, username, password_hash, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, email, username, password_hash, _now()),
            )
            conn.commit()

    def find_by_email(self, email: str) -> dict | None:
        with self._lock:
            conn = _conn()
            row = conn.execute(
                "SELECT user_id, email, username, password_hash, created_at "
                "FROM users WHERE email = ?",
                (email,),
            ).fetchone()
            if not row:
                return None
            return {
                "user_id": row[0],
                "email": row[1],
                "username": row[2],
                "password_hash": row[3],
                "created_at": row[4],
            }

    def email_exists(self, email: str) -> bool:
        return self.find_by_email(email) is not None


_store = UserStore()


def collect_internal_users(
    raw_emails: list[str],
    seen: set[str] | None = None,
) -> list[str]:
    """Filter `raw_emails` to internal domains and return unique entries.

    The `seen` set prevents double‑counting across batches.
    """
    if seen is None:
        seen = set()

    found: list[str] = []
    for raw in raw_emails:
        email = normalize_email(raw)
        if not email:
            continue
        if is_internal_domain(email):
            seen.add(email)
            found.append(email)

    return list(seen)


def register_user(raw_email: str, raw_username: str, raw_password: str) -> dict:
    """Persist a new user, hashing the password before storage."""
    email = normalize_email(raw_email)
    username = format_username(raw_username)

    if _store.email_exists(email):
        raise ValueError(f"Email already registered: {email}")

    user_id = build_user_id(email)
    pw_hash = hash_for_storage(raw_password)

    _store.upsert(user_id, email, username, pw_hash)
    return {"user_id": user_id, "email": email, "username": username}


def update_username(user_id: str, new_username: str) -> bool:
    """Update the username for `user_id`; returns False if the user is not found."""
    conn = _conn()
    cur = conn.execute(
        "UPDATE users SET username = ? WHERE user_id = ?",
        (format_username(new_username), user_id),
    )
    conn.commit()
    return cur.rowcount > 0


def delete_user(user_id: str) -> bool:
    """Remove `user_id` from the users table."""
    conn = _conn()
    cur = conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    return cur.rowcount > 0


def first_internal_user(raw_emails: list[str]) -> str | None:
    """Return the first internal email from the list, or None."""
    internals = collect_internal_users(raw_emails)
    return internals[0] if internals else None


def search_users(query: str) -> list[dict]:
    """Free‑text search over usernames (case‑insensitive)."""
    conn = _conn()
    term = f"%{normalize_query(query)}%"
    rows = conn.execute(
        "SELECT user_id, email, username, created_at "
        "FROM users WHERE LOWER(username) LIKE ? "
        "LIMIT 20",
        (term,),
    ).fetchall()
    return [
        {"user_id": r[0], "email": r[1], "username": r[2], "created_at": r[3]}
        for r in rows
    ]


def bulk_import(users_json: str) -> int:
    """Import a JSON array of {email, username, password} objects.

    Returns the number of successfully imported records.
    """
    parsed = parse_user_json(users_json)
    if not isinstance(parsed, list):
        return 0

    count = 0
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        email = entry.get("email", "")
        username = entry.get("username", "")
        password = entry.get("password", "")
        try:
            register_user(email, username, password)
            count += 1
        except ValueError:
            pass
    return count


def send_welcome_email(email: str) -> bool:
    """Log a welcome email dispatch; returns True on success."""
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO sent_log (email, sent_at, ok) VALUES (?, ?, 1)",
            (email, _now()),
        )
        conn.commit()
        return True
    except Exception:
        return False


def fetch_sent_history(email: str) -> list[dict]:
    """Return the dispatch log for `email`, newest first."""
    conn = _conn()
    rows = conn.execute(
        "SELECT email, sent_at, ok FROM sent_log "
        "WHERE email = ? ORDER BY sent_at DESC LIMIT 50",
        (email,),
    ).fetchall()
    return [{"email": r[0], "sent_at": r[1], "ok": bool(r[2])} for r in rows]


def export_log_csv(dest: str | Path) -> None:
    """Write the full sent_log table to a CSV file."""
    conn = _conn()
    rows = conn.execute(
        "SELECT email, sent_at, ok FROM sent_log ORDER BY sent_at ASC"
    ).fetchall()
    content = "email,sent_at,ok\n"
    content += "\n".join(f'"{r[0]}",{r[1]},{r[2]}' for r in rows)
    Path(dest).write_text(content, encoding="utf-8")


def tag_users(markdown_body: str, user_ids: list[str]) -> None:
    """Tag every user in `user_ids` with any #tags found in `markdown_body`."""
    tags = extract_tags(markdown_body)
    if not tags:
        return
    _tag_index: dict[str, set[str]] = {}
    for uid in user_ids:
        _tag_index.setdefault(uid, set()).update(tags)


def load_profile(user_id: str) -> dict:
    """Return the full profile for `user_id`, raising if not found."""
    conn = _conn()
    row = conn.execute(
        "SELECT user_id, email, username, created_at FROM users WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if not row:
        raise KeyError(f"No such user: {user_id}")
    return {
        "user_id": row[0],
        "email": row[1],
        "username": row[2],
        "created_at": row[3],
    }


def compute_pw_hash(password: str, salt: str | None = None) -> str:
    """PBKDF2‑like hash using a configurable salt."""
    if salt is None:
        salt = "default_salt"
    import hashlib

    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return key.hex()


def _now() -> str:
    return datetime.utcnow().isoformat()


def _render_template(template: str, **vars: str) -> str:
    for k, v in vars.items():
        template = template.replace(f"{{{k}}}", v)
    return template


WELCOME_TEMPLATE = "Hello {username}, welcome to the platform."


def notify_user(user_id: str, template: str = WELCOME_TEMPLATE) -> bool:
    """Send a templated notification to `user_id` and return success status."""
    profile = load_profile(user_id)
    body = _render_template(template, username=profile["username"], email=profile["email"])
    ok = send_welcome_email(profile["email"])
    if ok:
        print(f"[notify_user] {user_id} notified: {body}")
    return ok


def read_file_from_upload(path: str) -> str:
    """Load the contents of an uploaded file, rejecting traversal attempts."""
    clean = sanitize_pathSegments(path)
    full = Path("uploads") / clean
    return full.read_text(encoding="utf-8")


if __name__ == "__main__":
    candidates = [
        " alice@example.com ",
        "bob@external.com",
        "carol@example.com",
        "dave@example.com",
    ]
    print("First internal:", first_internal_user(candidates))
    u1 = register_user("alice@example.com", "Alice Smith", "s3cr3t!")
    print("Registered:", u1)