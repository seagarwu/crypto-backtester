from datetime import datetime

from orchestration_bootstrap import (
    build_run_name,
    init_autonomous_task,
    init_deep_research_run,
    slugify,
)


class TestOrchestrationBootstrap:
    def test_slugify_is_stable_and_ascii(self):
        assert slugify("BTC Mean Reversion / 1h") == "btc-mean-reversion-1h"
        assert slugify("   ") == "task"

    def test_build_run_name_includes_date_prefix(self):
        run_name = build_run_name("Mean Reversion", now=datetime(2026, 3, 17, 10, 0, 0))

        assert run_name.startswith("20260317-mean-reversion-")

    def test_init_autonomous_task_creates_expected_files(self, tmp_path):
        paths = init_autonomous_task(
            project_root=str(tmp_path),
            task_name="strategy loop",
            description="Iterate on BBand strategy",
            goals=["Record human checkpoint"],
        )

        assert paths.root.exists()
        assert paths.task_list.exists()
        assert paths.progress.exists()
        assert paths.session_id.exists()
        assert paths.session_log.exists()
        assert "Record human checkpoint" in paths.task_list.read_text(encoding="utf-8")
        assert "Respect human checkpoints" in paths.brief.read_text(encoding="utf-8")

    def test_init_deep_research_run_creates_expected_workspace(self, tmp_path):
        paths = init_deep_research_run(
            project_root=str(tmp_path),
            topic="btc mean reversion",
            question="Which family is worth testing next?",
            dimensions=["market regime", "risk controls"],
            now=datetime(2026, 3, 17, 10, 0, 0),
        )

        assert paths.root.exists()
        assert paths.prompts.is_dir()
        assert paths.logs.is_dir()
        assert paths.child_outputs.is_dir()
        assert paths.raw.is_dir()
        assert paths.cache.is_dir()
        assert paths.tmp.is_dir()
        manifest = paths.manifest.read_text(encoding="utf-8")
        assert "- Topic: btc mean reversion" in manifest
        assert "- market regime" in manifest
