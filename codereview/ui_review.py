"""Helpers for previewing codereview file mutations in the Streamlit UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from codereview.llm import assist_file
from codereview.patcher import CopilotResult, clean, inject, unified_diff


class FileValidationError(ValueError):
    """Raised when a UI-provided file path is not reviewable."""


@dataclass(frozen=True)
class ReviewPreview:
    """A pending file mutation that can be displayed before writing."""

    target: Path
    original: str
    updated: str
    diff: str
    summary: str
    logs: tuple[str, ...] = ()

    @property
    def has_changes(self) -> bool:
        return self.updated != self.original


Reviewer = Callable[[Path, str], CopilotResult]


def validate_python_file(raw_path: str) -> Path:
    """Resolve and validate a local Python file path for UI review."""
    text = raw_path.strip()
    if not text:
        raise FileValidationError("Enter a local Python file path.")

    path = Path(text).expanduser().resolve()
    if not path.exists():
        raise FileValidationError(f"File not found: {text}")
    if not path.is_file():
        raise FileValidationError(f"Not a file: {text}")
    if path.suffix != ".py":
        raise FileValidationError("Only .py files are supported.")
    return path


def build_review_preview(
    target: Path,
    message: str,
    reviewer: Reviewer | None = None,
    log_sink: Callable[[str], None] | None = None,
) -> ReviewPreview:
    """Run codereview and return a preview without mutating the source file."""
    instruction = message.strip()
    if not instruction:
        raise FileValidationError("Enter a review instruction.")

    original = target.read_text(encoding="utf-8")
    logs: list[str] = []
    def collect_log(message: str) -> None:
        logs.append(message)
        if log_sink is not None:
            log_sink(message)

    if reviewer is None:
        result = assist_file(target, instruction, log_sink=collect_log)
    else:
        result = reviewer(target, instruction)

    if result.rewritten_source is not None:
        updated = result.rewritten_source
        if original.endswith("\n") and not updated.endswith("\n"):
            updated += "\n"
        summary = f"Focused rewrite preview for {target}"
    else:
        updated = inject(original, result.reviews)
        added = sum(len(comments) for comments in result.reviews.values())
        summary = f"{added} review comments previewed for {target}"

    return ReviewPreview(
        target=target,
        original=original,
        updated=updated,
        diff=unified_diff(str(target), original, updated),
        summary=summary,
        logs=tuple(logs),
    )


def build_cleanup_preview(target: Path) -> ReviewPreview:
    """Return a preview for removing injected # REVIEW comments."""
    original = target.read_text(encoding="utf-8")
    updated, removed = clean(original)
    return ReviewPreview(
        target=target,
        original=original,
        updated=updated,
        diff=unified_diff(str(target), original, updated),
        summary=f"{removed} review comments previewed for removal from {target}",
    )


def apply_preview(preview: ReviewPreview) -> None:
    """Write a previously previewed mutation to disk."""
    preview.target.write_text(preview.updated, encoding="utf-8")
