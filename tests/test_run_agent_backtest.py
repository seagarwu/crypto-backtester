import argparse

from scripts.run_agent_backtest import (
    build_backtest_command,
    collect_strategy_params,
    coerce_cli_value,
    parse_param_overrides,
)


def build_args(**overrides):
    defaults = {
        "data": "data/BTCUSDT_1h.csv",
        "strategy": "ma_crossover",
        "iteration": 2,
        "symbol": "BTCUSDT",
        "interval": "1h",
        "start": "2024-01-01",
        "end": "2024-12-31",
        "short_window": None,
        "long_window": None,
        "bband_period": None,
        "bband_std": None,
        "ma_period": None,
        "entry_threshold": None,
        "exit_threshold": None,
        "use_ma_confirm": None,
        "require_confirm": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class TestRunAgentBacktestHelpers:
    def test_coerce_cli_value_handles_common_types(self):
        assert coerce_cli_value("true") is True
        assert coerce_cli_value("12") == 12
        assert coerce_cli_value("3.5") == 3.5
        assert coerce_cli_value("demo") == "demo"

    def test_parse_param_overrides_parses_key_value_pairs(self):
        params = parse_param_overrides(["alpha=1", "enabled=true", "name=test"])

        assert params == {"alpha": 1, "enabled": True, "name": "test"}

    def test_parse_param_overrides_rejects_invalid_pairs(self):
        try:
            parse_param_overrides(["broken"])
        except ValueError as exc:
            assert "KEY=VALUE" in str(exc)
        else:
            raise AssertionError("Expected ValueError for invalid param override")

    def test_collect_strategy_params_merges_explicit_flags_and_extra_params(self):
        args = build_args(short_window=20, long_window=50)

        params = collect_strategy_params(args, ["use_ma_confirm=true", "risk=low"])

        assert params["short_window"] == 20
        assert params["long_window"] == 50
        assert params["use_ma_confirm"] is True
        assert params["risk"] == "low"

    def test_build_backtest_command_is_stable_and_explicit(self):
        args = build_args(short_window=20, long_window=50)
        command = build_backtest_command(args, {"long_window": 50, "short_window": 20})

        assert command.startswith("python scripts/run_agent_backtest.py")
        assert "--data data/BTCUSDT_1h.csv" in command
        assert "--param long_window=50" in command
        assert "--param short_window=20" in command
