"""injects review comments into source, strips them on clean, builds unified diffs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import difflib
import re

REVIEW_PREFIX = "# REVIEW:"
_REVIEW_RE = re.compile(r"^REVIEW:(\d+):\s*(.+)$")
FILE_START = "FILE_START"
FILE_END = "FILE_END"


@dataclass(frozen=True)
class CopilotResult:
    reviews: dict[int, list[str]]
    rewritten_source: str | None = None


def parse_reviews(text: str) -> dict[int, list[str]]:
    """Turn raw LLM output into {line_number: [comments]}. Ignores non-REVIEW lines."""
    out: dict[int, list[str]] = {}
    for line in text.splitlines():
        m = _REVIEW_RE.match(line.strip())
        if m:
            lineno = int(m.group(1))
            out.setdefault(lineno, []).append(m.group(2).strip())
    return out


def parse_copilot_result(text: str) -> CopilotResult:
    """Parse either inline review comments or a full-file rewrite response."""
    lines = text.splitlines()
    try:
        start = lines.index(FILE_START)
        end = lines.index(FILE_END)
    except ValueError:
        return CopilotResult(reviews=parse_reviews(text))

    if start >= end:
        raise ValueError("Invalid copilot rewrite response: FILE_END appears before FILE_START")

    rewritten = "\n".join(lines[start + 1 : end])
    return CopilotResult(reviews={}, rewritten_source=rewritten)


def inject(source: str, reviews: Mapping[int, str | Sequence[str]]) -> str:
    """Insert # REVIEW: comments above flagged lines, preserving indentation."""
    lines = source.splitlines(keepends=True)
    for lineno in sorted(reviews.keys(), reverse=True):
        if not 1 <= lineno <= len(lines):
            continue
        target = lines[lineno - 1]
        indent = target[: len(target) - len(target.lstrip())]
        review = reviews[lineno]
        comments = [review] if isinstance(review, str) else list(review)
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
