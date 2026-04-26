"""injects review comments into source, strips them on clean, builds unified diffs."""

from __future__ import annotations

import difflib
import re

REVIEW_PREFIX = "# REVIEW:"
_REVIEW_RE = re.compile(r"^REVIEW:(\d+):\s*(.+)$")


def parse_reviews(text: str) -> dict[int, list[str]]:
    """Turn raw LLM output into {line_number: [comments]}. Ignores non-REVIEW lines."""
    out: dict[int, list[str]] = {}
    for line in text.splitlines():
        m = _REVIEW_RE.match(line.strip())
        if m:
            lineno = int(m.group(1))
            out.setdefault(lineno, []).append(m.group(2).strip())
    return out


def inject(source: str, reviews: dict[int, str | list[str]]) -> str:
    """Insert # REVIEW: comments above flagged lines, preserving indentation."""
    lines = source.splitlines(keepends=True)
    for lineno in sorted(reviews.keys(), reverse=True):
        if not 1 <= lineno <= len(lines):
            continue
        target = lines[lineno - 1]
        indent = target[: len(target) - len(target.lstrip())]
        review = reviews[lineno]
        comments = review if isinstance(review, list) else [review]
        for comment in reversed(comments):
            lines.insert(lineno - 1, f"{indent}{REVIEW_PREFIX} {comment}\n")
    return "".join(lines)


def clean(source: str) -> tuple[str, int]:
    """Strip all # REVIEW: lines. Returns (cleaned_source, count_removed)."""
    kept: list[str] = []
    removed = 0
    for line in source.splitlines(keepends=True):
        if line.strip().startswith(REVIEW_PREFIX):
            removed += 1
        else:
            kept.append(line)
    return "".join(kept), removed


def unified_diff(path: str, before: str, after: str) -> str:
    """Return a unified diff string between before and after. Used for --dry-run."""
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=path,
            tofile=path,
        )
    )
