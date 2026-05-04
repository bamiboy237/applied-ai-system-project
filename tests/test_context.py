from __future__ import annotations

from pathlib import Path

from codereview.context import iter_context_files, is_context_candidate


def test_context_file_iteration_excludes_generated_and_dependency_dirs(tmp_path: Path) -> None:
    keep = tmp_path / "app.py"
    keep.write_text("def app():\n    return True\n", encoding="utf-8")

    excluded_files = [
        tmp_path / ".venv" / "lib.py",
        tmp_path / "__pycache__" / "cached.py",
        tmp_path / ".git" / "hook.py",
        tmp_path / "node_modules" / "pkg.py",
        tmp_path / "dist" / "generated.py",
    ]
    for file in excluded_files:
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("def generated():\n    return False\n", encoding="utf-8")

    assert iter_context_files(tmp_path) == [keep]
    assert is_context_candidate(keep, tmp_path)
    assert not any(is_context_candidate(file, tmp_path) for file in excluded_files)
