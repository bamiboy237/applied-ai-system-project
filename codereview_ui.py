"""Launcher for the BugHound Streamlit UI."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def streamlit_target() -> Path:
    """Return the BugHound app path relative to this launcher module."""
    return Path(__file__).resolve().parent / "bughound_app.py"


def find_streamlit() -> str | None:
    """Find Streamlit on PATH or in the repo-local virtual environment."""
    streamlit = shutil.which("streamlit")
    if streamlit is not None:
        return streamlit

    local_streamlit = Path(__file__).resolve().parent / ".venv" / "bin" / "streamlit"
    if local_streamlit.exists():
        return str(local_streamlit)
    return None


def main() -> int:
    """Launch Streamlit with a clear error when it is unavailable."""
    streamlit = find_streamlit()
    if streamlit is None:
        print(
            "Streamlit is not installed or is not on PATH. "
            "Install dependencies with `pip install -r requirements.txt`.",
            file=sys.stderr,
        )
        return 1

    app_path = streamlit_target()
    if not app_path.exists():
        print(f"BugHound app not found at {app_path}", file=sys.stderr)
        return 1

    return subprocess.run(
        [streamlit, "run", str(app_path)],
        check=False,
        cwd=app_path.parent,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
