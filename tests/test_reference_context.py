from agents.reference_context import (
    CachedEngineerReferenceProvider,
    CompositeEngineerReferenceProvider,
    EngineerReferenceRequest,
    RepoPatternReferenceProvider,
)


def test_repo_pattern_reference_provider_returns_repo_native_patterns():
    provider = RepoPatternReferenceProvider()

    payload = provider.build(
        EngineerReferenceRequest(
            strategy_name="BTCUSDT_BBand_Reversion",
            indicators=["BBand", "Volume"],
            feedback={"validation_issues": ["syntax error"]},
            prior_attempts=[{"failure_categories": ["syntax"]}],
            route_family="multi_timeframe_bband_reversion",
        )
    )

    assert payload["provider"] == "repo_patterns"
    assert payload["repo_patterns"][0]["pattern"] == "multi_timeframe_bband_reversion"
    assert "syntax" in payload["repeated_failure_categories"]
    assert payload["route_family"] == "multi_timeframe_bband_reversion"


def test_composite_reference_provider_merges_sources_without_dup_guardrails():
    provider = CompositeEngineerReferenceProvider(providers=[RepoPatternReferenceProvider()])

    payload = provider.build(
        EngineerReferenceRequest(
            strategy_name="MA Demo",
            indicators=["MA"],
        )
    )

    assert payload["sources"] == ["repo_patterns"]
    assert payload["repo_patterns"][0]["pattern"] == "ma_crossover"
    assert len(payload["guardrails"]) == len(set(payload["guardrails"]))


def test_cached_reference_provider_reads_matching_curated_entries(tmp_path):
    cache_path = tmp_path / "engineer_reference_cache.json"
    cache_path.write_text(
        '[{"name":"Ext BBand","source_type":"github","summary":"Borrow structure","tags":["bband","volume"],"patterns":["multi_timeframe_bband_reversion"]}]',
        encoding="utf-8",
    )
    provider = CachedEngineerReferenceProvider(str(cache_path))

    payload = provider.build(
        EngineerReferenceRequest(
            strategy_name="BBand Demo",
            indicators=["BBand", "Volume"],
            route_family="multi_timeframe_bband_reversion",
        )
    )

    assert payload["provider"] == "reference_cache"
    assert payload["external_references"][0]["name"] == "Ext BBand"
