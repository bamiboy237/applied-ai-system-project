from __future__ import annotations

import subprocess

import codereview_ui


def test_streamlit_target_resolves_repo_app() -> None:
    target = codereview_ui.streamlit_target()

    assert target.name == "bughound_app.py"
    assert target.exists()


def test_launcher_reports_missing_streamlit(monkeypatch, capsys) -> None:
    monkeypatch.setattr(codereview_ui, "find_streamlit", lambda: None)

    assert codereview_ui.main() == 1
    captured = capsys.readouterr()
    assert "Streamlit is not installed" in captured.err


def test_launcher_runs_streamlit_with_resolved_app(monkeypatch) -> None:
    calls = {}
    monkeypatch.setattr(codereview_ui, "find_streamlit", lambda: "/bin/streamlit")

    def fake_run(command, check):
        calls["command"] = command
        calls["check"] = check
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(codereview_ui.subprocess, "run", fake_run)

    assert codereview_ui.main() == 0
    assert calls["command"] == [
        "/bin/streamlit",
        "run",
        str(codereview_ui.streamlit_target()),
    ]
    assert calls["check"] is False
