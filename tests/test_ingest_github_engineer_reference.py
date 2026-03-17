import json
import subprocess
from pathlib import Path

from scripts import ingest_github_engineer_reference as script


def test_resolve_gitmcp_script_prefers_explicit_path(tmp_path):
    script_path = tmp_path / "gitmcp.py"
    script_path.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    resolved = script.resolve_gitmcp_script(str(script_path))

    assert resolved == script_path


def test_run_gitmcp_returns_stdout(monkeypatch, tmp_path):
    script_path = tmp_path / "gitmcp.py"
    script_path.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    def fake_run(cmd, check, capture_output, text):
        assert cmd[1] == str(script_path)
        return subprocess.CompletedProcess(cmd, 0, stdout="docs output", stderr="")

    monkeypatch.setattr(script.subprocess, "run", fake_run)

    output = script.run_gitmcp(script_path, "fetch-docs", "owner/repo")

    assert output == "docs output"


def test_main_appends_github_reference(monkeypatch, tmp_path):
    script_path = tmp_path / "gitmcp.py"
    script_path.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    research_dir = tmp_path / "research"

    def fake_run_gitmcp(resolved_script_path, command, repo, query=""):
        if command == "fetch-docs":
            return "This repo implements a BBand strategy."
        if command == "search-code":
            return "strategy.py: class BBandStrategy"
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(script, "run_gitmcp", fake_run_gitmcp)
    monkeypatch.setattr(
        "sys.argv",
        [
            "ingest_github_engineer_reference.py",
            "owner/repo",
            "--query",
            "BBandStrategy",
            "--tag",
            "bband",
            "--pattern",
            "multi_timeframe_bband_reversion",
            "--gitmcp-script",
            str(script_path),
            "--research-dir",
            str(research_dir),
        ],
    )

    script.main()

    payload = json.loads((research_dir / "engineer_reference_cache.json").read_text(encoding="utf-8"))
    assert payload[0]["source_type"] == "github"
    assert payload[0]["repo"] == "owner/repo"
    assert "BBandStrategy" in payload[0]["summary"]
