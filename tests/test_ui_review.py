from __future__ import annotations

from pathlib import Path

import pytest

from codereview.patcher import CopilotResult
from codereview.ui_review import (
    FileValidationError,
    apply_preview,
    build_cleanup_preview,
    build_review_preview,
    validate_python_file,
)


def test_validate_python_file_accepts_existing_python_file(tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("print('hi')\n", encoding="utf-8")

    assert validate_python_file(str(target)) == target.resolve()


def test_validate_python_file_rejects_missing_and_non_python_paths(tmp_path: Path) -> None:
    with pytest.raises(FileValidationError, match="File not found"):
        validate_python_file(str(tmp_path / "missing.py"))

    target = tmp_path / "sample.txt"
    target.write_text("hello\n", encoding="utf-8")

    with pytest.raises(FileValidationError, match="Only .py files"):
        validate_python_file(str(target))


def test_build_review_preview_injects_comments_without_writing(tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    original = "print('hi')\n"
    target.write_text(original, encoding="utf-8")

    preview = build_review_preview(
        target,
        "review this file",
        reviewer=lambda path, message: CopilotResult(
            reviews={1: ["avoid print in committed code"]}
        ),
    )

    assert preview.has_changes
    assert "+# REVIEW: avoid print in committed code" in preview.diff
    assert preview.logs == ()
    assert target.read_text(encoding="utf-8") == original

    apply_preview(preview)

    assert target.read_text(encoding="utf-8") == (
        "# REVIEW: avoid print in committed code\nprint('hi')\n"
    )


def test_build_review_preview_forwards_live_logs(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("print('hi')\n", encoding="utf-8")
    live_logs: list[str] = []

    def fake_assist_file(path: Path, message: str, log_sink=None) -> CopilotResult:
        if log_sink is not None:
            log_sink("starting model turn 1")
            log_sink("model requested tool `read_file`")
        return CopilotResult(reviews={1: ["avoid print"]})

    monkeypatch.setattr("codereview.ui_review.assist_file", fake_assist_file)

    preview = build_review_preview(
        target,
        "review this file",
        log_sink=live_logs.append,
    )

    assert live_logs == ["starting model turn 1", "model requested tool `read_file`"]
    assert preview.logs == tuple(live_logs)


def test_build_review_preview_preserves_rewrite_trailing_newline(tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("print('old')\n", encoding="utf-8")

    preview = build_review_preview(
        target,
        "fix this file",
        reviewer=lambda path, message: CopilotResult(
            reviews={},
            rewritten_source="print('new')",
        ),
    )

    assert preview.updated == "print('new')\n"
    assert "+print('new')" in preview.diff


def test_build_cleanup_preview_removes_review_comments_without_writing(tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    original = "# REVIEW: avoid print\nprint('hi')\n"
    target.write_text(original, encoding="utf-8")

    preview = build_cleanup_preview(target)

    assert preview.updated == "print('hi')\n"
    assert "-# REVIEW: avoid print" in preview.diff
    assert target.read_text(encoding="utf-8") == original
