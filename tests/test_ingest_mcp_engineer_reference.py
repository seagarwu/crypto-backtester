import json

from scripts import ingest_mcp_engineer_reference as script


def test_load_summary_prefers_inline_text(tmp_path):
    summary_file = tmp_path / "summary.txt"
    summary_file.write_text("file summary", encoding="utf-8")

    summary = script.load_summary("inline summary", str(summary_file))

    assert summary == "inline summary"


def test_load_metadata_parses_json():
    payload = script.load_metadata('{"source":"firecrawl","score":0.9}')

    assert payload["source"] == "firecrawl"
    assert payload["score"] == 0.9


def test_main_appends_mcp_reference(monkeypatch, tmp_path):
    research_dir = tmp_path / "research"

    monkeypatch.setattr(
        "sys.argv",
        [
            "ingest_mcp_engineer_reference.py",
            "--name",
            "Firecrawl summary",
            "--server",
            "firecrawl",
            "--resource-uri",
            "https://example.com/page",
            "--summary",
            "Use the risk-control section as pattern guidance.",
            "--metadata-json",
            '{"topic":"risk-controls"}',
            "--tag",
            "risk",
            "--pattern",
            "reference_guided_synthesis",
            "--research-dir",
            str(research_dir),
        ],
    )

    script.main()

    payload = json.loads((research_dir / "engineer_reference_cache.json").read_text(encoding="utf-8"))
    assert payload[0]["source_type"] == "mcp"
    assert payload[0]["mcp_server"] == "firecrawl"
    assert payload[0]["metadata"]["topic"] == "risk-controls"
