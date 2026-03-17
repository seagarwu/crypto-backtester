import json

from scripts import ingest_skill_engineer_reference as script


def test_extract_skill_summary_trims_frontmatter_and_whitespace(tmp_path):
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "---\nname: demo\n---\n\n# Demo Skill\n\nUse this skill to do repo work.\n",
        encoding="utf-8",
    )

    summary = script.extract_skill_summary(skill)

    assert "name: demo" not in summary
    assert "Demo Skill" in summary
    assert "repo work" in summary


def test_main_appends_skill_reference(monkeypatch, tmp_path):
    skill = tmp_path / "demo-skill" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text("# Demo Skill\nUse it for careful engineering.\n", encoding="utf-8")
    research_dir = tmp_path / "research"

    monkeypatch.setattr(
        "sys.argv",
        [
            "ingest_skill_engineer_reference.py",
            str(skill),
            "--tag",
            "engineering",
            "--pattern",
            "repo_native_repair",
            "--research-dir",
            str(research_dir),
        ],
    )

    script.main()

    payload = json.loads((research_dir / "engineer_reference_cache.json").read_text(encoding="utf-8"))
    assert payload[0]["source_type"] == "skill"
    assert payload[0]["skill_path"] == str(skill.resolve())
    assert "careful engineering" in payload[0]["summary"]
