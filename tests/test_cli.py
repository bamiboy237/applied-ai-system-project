from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from codereview.codereview import app
from codereview.patcher import CopilotResult

runner = CliRunner()


def test_clean_removes_existing_review_comments(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text(
        '# REVIEW: first\nprint("hi")\n',
        encoding="utf-8",
    )

    result = runner.invoke(app, ["--file", str(target), "--clean"])

    assert result.exit_code == 0
    assert "1 review comments removed" in result.stdout
    assert f"cleaning teacher comments in {target.resolve()}" in result.stderr
    assert target.read_text(encoding="utf-8") == 'print("hi")\n'


def test_standard_review_injects_comments(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("x = 1\nprint(x)\n", encoding="utf-8")
    monkeypatch.setattr(
        "codereview.codereview.review_file",
        lambda path, message: CopilotResult(
            reviews={2: ["use structured logging instead of print"]}
        ),
    )

    result = runner.invoke(app, ["--file", str(target), "review this"])

    assert result.exit_code == 0
    assert "1 reviews added" in result.stdout
    assert f"assisting {target.resolve()}" in result.stderr
    assert target.read_text(encoding="utf-8") == (
        "x = 1\n# REVIEW: use structured logging instead of print\nprint(x)\n"
    )


def test_lines_option_filters_reviews_and_updates_prompt(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("a = 1\nb = 2\nprint(a + b)\n", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_review_file(path: Path, message: str) -> CopilotResult:
        captured["path"] = path
        captured["message"] = message
        return CopilotResult(reviews={3: ["avoid print in library code"]})

    monkeypatch.setattr("codereview.codereview.review_file", fake_review_file)

    result = runner.invoke(
        app,
        ["--file", str(target), "--lines", "3-3", "focus this range"],
    )

    assert result.exit_code == 0
    assert captured["path"] == target.resolve()
    assert "Only comment on or change lines 3-3" in str(captured["message"])
    assert target.read_text(encoding="utf-8") == (
        "a = 1\nb = 2\n# REVIEW: avoid print in library code\nprint(a + b)\n"
    )


def test_lines_option_rejects_out_of_range_reviews(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("a = 1\nb = 2\nprint(a + b)\n", encoding="utf-8")
    monkeypatch.setattr(
        "codereview.codereview.review_file",
        lambda path, message: CopilotResult(reviews={1: ["out of range"]}),
    )

    with pytest.raises(RuntimeError, match="outside requested line range: 1"):
        runner.invoke(
            app,
            ["--file", str(target), "--lines", "3-3", "focus this range"],
            catch_exceptions=False,
        )


def test_dry_run_applies_patch_when_confirmed(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("print('x')\n", encoding="utf-8")
    monkeypatch.setattr(
        "codereview.codereview.review_file",
        lambda path, message: CopilotResult(
            reviews={1: ["avoid print in committed code"]}
        ),
    )
    monkeypatch.setattr("codereview.codereview.open_in_editor", lambda path, line=1: True)

    result = runner.invoke(
        app,
        ["--file", str(target), "--dry-run", "review"],
        input="y\n",
    )

    assert result.exit_code == 0
    assert "1 reviews added" in result.stdout
    assert "opening diff /tmp/codereview_sample_" in result.stderr
    assert f"applying patch to {target.resolve()}" in result.stderr
    assert target.read_text(encoding="utf-8") == (
        "# REVIEW: avoid print in committed code\nprint('x')\n"
    )


def test_dry_run_leaves_source_unchanged_when_rejected(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("print('x')\n", encoding="utf-8")
    monkeypatch.setattr(
        "codereview.codereview.review_file",
        lambda path, message: CopilotResult(
            reviews={1: ["avoid print in committed code"]}
        ),
    )
    monkeypatch.setattr("codereview.codereview.open_in_editor", lambda path, line=1: True)

    result = runner.invoke(
        app,
        ["--file", str(target), "--dry-run", "review"],
        input="n\n",
    )

    assert result.exit_code == 0
    assert "Diff available at" in result.stdout
    assert target.read_text(encoding="utf-8") == "print('x')\n"


def test_dry_run_short_circuits_when_no_changes(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("print('x')\n", encoding="utf-8")
    monkeypatch.setattr(
        "codereview.codereview.review_file",
        lambda path, message: CopilotResult(reviews={}),
    )
    monkeypatch.setattr("codereview.codereview.open_in_editor", lambda path, line=1: True)

    result = runner.invoke(app, ["--file", str(target), "--dry-run", "review"])

    assert result.exit_code == 0
    assert "No changes to apply." in result.stdout
    assert target.read_text(encoding="utf-8") == "print('x')\n"


def test_clean_rejects_message_and_dry_run(tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("print('x')\n", encoding="utf-8")

    result = runner.invoke(app, ["--file", str(target), "--clean", "--dry-run"])
    assert result.exit_code != 0
    assert "--clean cannot be used with --dry-run" in result.output

    result = runner.invoke(app, ["--file", str(target), "--clean", "review"])
    assert result.exit_code != 0
    assert "--clean cannot be used with a review message" in result.output


def test_non_python_file_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("hello\n", encoding="utf-8")

    result = runner.invoke(app, ["--file", str(target), "review"])

    assert result.exit_code != 0
    assert "Only Python files are supported" in result.output


def test_standard_copilot_rewrite_updates_file(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("print('old')\n", encoding="utf-8")
    monkeypatch.setattr(
        "codereview.codereview.review_file",
        lambda path, message: CopilotResult(
            reviews={},
            rewritten_source="print('new')",
        ),
    )

    result = runner.invoke(app, ["--file", str(target), "fix this file"])

    assert result.exit_code == 0
    assert f"updated {target.resolve()}" in result.stdout
    assert target.read_text(encoding="utf-8") == "print('new')\n"


def test_dry_run_copilot_rewrite_applies_when_confirmed(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("print('old')\n", encoding="utf-8")
    monkeypatch.setattr(
        "codereview.codereview.review_file",
        lambda path, message: CopilotResult(
            reviews={},
            rewritten_source="print('new')",
        ),
    )
    monkeypatch.setattr("codereview.codereview.open_in_editor", lambda path, line=1: True)

    result = runner.invoke(
        app,
        ["--file", str(target), "--dry-run", "fix this file"],
        input="y\n",
    )

    assert result.exit_code == 0
    assert f"updated {target.resolve()}" in result.stdout
    assert target.read_text(encoding="utf-8") == "print('new')\n"
