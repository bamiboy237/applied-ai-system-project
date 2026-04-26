"""CLI entrypoint for teacher-style code guidance and focused file edits."""

from __future__ import annotations

import hashlib
import os
import shlex
import shutil
import subprocess
from pathlib import Path

import typer

from codereview.llm import assist_file
from codereview.patcher import clean, inject, unified_diff

app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)
review_file = assist_file


def _resolve_target(file_path: Path) -> Path:
    """Resolve, validate, and restrict the target file to a Python source file."""
    path = file_path.expanduser().resolve()
    if not path.exists():
        raise typer.BadParameter(f"File not found: {file_path}")
    if not path.is_file():
        raise typer.BadParameter(f"Not a file: {file_path}")
    if path.suffix != ".py":
        raise typer.BadParameter("Only Python files are supported")
    return path


def _parse_lines(raw_lines: str | None) -> tuple[int, int] | None:
    """Parse an optional A-B line range argument."""
    if raw_lines is None:
        return None

    start_text, sep, end_text = raw_lines.partition("-")
    if sep != "-" or not start_text or not end_text:
        raise typer.BadParameter("Line range must look like A-B")

    try:
        start = int(start_text)
        end = int(end_text)
    except ValueError as exc:
        raise typer.BadParameter("Line range must look like A-B") from exc

    if start < 1 or end < 1 or start > end:
        raise typer.BadParameter("Line range must be positive and ascending")

    return start, end


def _validate_reviews_in_range(
    reviews: dict[int, list[str]], lines: tuple[int, int] | None
) -> None:
    """Reject reviews that fall outside the requested line range."""
    if lines is None:
        return
    start, end = lines
    invalid = sorted(lineno for lineno in reviews if not start <= lineno <= end)
    if invalid:
        joined = ", ".join(str(lineno) for lineno in invalid)
        raise RuntimeError(
            f"Model returned reviews outside requested line range: {joined}"
        )


def open_in_editor(path: Path, line: int = 1) -> bool:
    """Open a file in the configured editor and report whether it succeeded."""
    editor = os.environ.get("EDITOR", "zed")
    editor_parts = shlex.split(editor)
    if not editor_parts:
        typer.echo(f"Editor unavailable. Diff saved to {path}")
        return False

    name = Path(editor_parts[0]).name
    commands = {
        "code": [*editor_parts, "--goto", f"{path}:{line}"],
        "zed": [*editor_parts, f"{path}:{line}"],
        "nvim": [*editor_parts, f"+{line}", str(path)],
        "vim": [*editor_parts, f"+{line}", str(path)],
    }
    command = commands.get(name, [*editor_parts, str(path)])

    executable = command[0]
    if shutil.which(executable) is None:
        typer.echo(f"Editor '{executable}' not found. Diff saved to {path}")
        return False

    try:
        subprocess.run(command, check=False)
    except OSError:
        typer.echo(f"Failed to open editor. Diff saved to {path}")
        return False
    return True


@app.command()
def main(
    message: str | None = typer.Argument(
        None,
        help="Instruction for the model.",
    ),
    file: Path = typer.Option(
        ...,
        "--file",
        help="Path to the Python file to review.",
    ),
    lines: str | None = typer.Option(
        None,
        "--lines",
        help="Optional review range formatted as A-B.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview the diff in a temp file before applying it.",
    ),
    clean_only: bool = typer.Option(
        False,
        "--clean",
        help="Remove existing injected # REVIEW comments.",
    ),
) -> None:
    """Run the review or clean command for a single Python file."""
    if clean_only:
        if dry_run:
            raise typer.BadParameter("--clean cannot be used with --dry-run")
        if message is not None:
            raise typer.BadParameter("--clean cannot be used with a review message")
    elif message is None:
        raise typer.BadParameter("A review message is required unless --clean is set")

    target = _resolve_target(file)
    line_range = _parse_lines(lines)
    original = target.read_text(encoding="utf-8")

    if clean_only:
        typer.echo(f"cleaning teacher comments in {target}", err=True)
        cleaned, removed = clean(original)
        if cleaned != original:
            target.write_text(cleaned, encoding="utf-8")
        typer.echo(f"{removed} review comments removed from {target}")
        raise typer.Exit()

    if message is None:
        raise RuntimeError("Instruction was unexpectedly missing after validation")

    review_message = message
    if line_range is not None:
        start, end = line_range
        review_message = (
            f"{message}\n\nOnly comment on or change lines {start}-{end}. Ignore all other lines."
        )

    typer.echo(f"assisting {target}", err=True)
    result = review_file(target, message=review_message)

    if result.rewritten_source is not None:
        updated = result.rewritten_source
        if original.endswith("\n") and not updated.endswith("\n"):
            updated += "\n"
        added = 0
        action_summary = f"updated {target}"
    else:
        reviews = result.reviews
        _validate_reviews_in_range(reviews, line_range)
        updated = inject(original, reviews)
        added = sum(len(comments) for comments in reviews.values())
        action_summary = f"{added} reviews added to {target}"

    if dry_run:
        diff = unified_diff(str(target), original, updated)
        if not diff:
            typer.echo("No changes to apply.")
            raise typer.Exit()
        digest = hashlib.sha1(str(target.resolve()).encode("utf-8")).hexdigest()[:10]
        diff_path = Path("/tmp") / f"codereview_{target.stem}_{digest}.diff"
        diff_path.write_text(diff, encoding="utf-8")
        typer.echo(f"opening diff {diff_path}", err=True)
        open_in_editor(diff_path)

        if input("Apply patch? [y/N] ").strip().lower() == "y":
            typer.echo(f"applying patch to {target}", err=True)
            target.write_text(updated, encoding="utf-8")
            typer.echo(action_summary)
        else:
            typer.echo(f"Diff available at {diff_path}")
        raise typer.Exit()

    if updated != original:
        target.write_text(updated, encoding="utf-8")
    typer.echo(action_summary)


if __name__ == "__main__":
    app()
