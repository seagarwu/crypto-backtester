#!/usr/bin/env python3
"""Run a standardized backtest-agent step and write canonical research artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research_contracts import ResearchArtifactWriter


def coerce_cli_value(value: str) -> Any:
    lowered = value.strip().lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def parse_param_overrides(pairs: Iterable[str]) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"Expected KEY=VALUE format, got: {pair}")
        key, raw_value = pair.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Parameter key cannot be empty: {pair}")
        params[key] = coerce_cli_value(raw_value.strip())
    return params


def collect_strategy_params(args: argparse.Namespace, extra_params: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    params = parse_param_overrides(extra_params or [])
    explicit = {
        "short_window": args.short_window,
        "long_window": args.long_window,
        "bband_period": args.bband_period,
        "bband_std": args.bband_std,
        "ma_period": args.ma_period,
        "entry_threshold": args.entry_threshold,
        "exit_threshold": args.exit_threshold,
        "use_ma_confirm": args.use_ma_confirm,
        "require_confirm": args.require_confirm,
    }
    for key, value in explicit.items():
        if value is not None:
            params[key] = value
    return params


def build_backtest_command(args: argparse.Namespace, strategy_params: Dict[str, Any]) -> str:
    command = [
        "python",
        "scripts/run_agent_backtest.py",
        f"--data {args.data}",
        f"--strategy {args.strategy}",
        f"--iteration {args.iteration}",
        f"--symbol {args.symbol}",
        f"--interval {args.interval}",
    ]
    if args.start:
        command.append(f"--start {args.start}")
    if args.end:
        command.append(f"--end {args.end}")
    for key in sorted(strategy_params):
        command.append(f"--param {key}={strategy_params[key]}")
    return " ".join(command)


def build_strategy_stub(
    strategy_name: str,
    strategy_params: Dict[str, Any],
    timeframe: str,
) -> Any:
    indicators_map = {
        "ma_crossover": ["MA"],
        "bband": ["BBand"],
        "multi_timeframe_bband": ["BBand", "MA"],
    }
    return type(
        "StrategyStub",
        (),
        {
            "name": strategy_name,
            "description": f"Backtest-agent run for {strategy_name}",
            "indicators": indicators_map.get(strategy_name, []),
            "entry_rules": "",
            "exit_rules": "",
            "parameters": strategy_params,
            "timeframe": timeframe,
            "risk_level": "medium",
        },
    )()


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run standardized backtest-agent flow")
    parser.add_argument("--data", required=True, help="Path to data CSV for the backtest")
    parser.add_argument("--strategy", required=True, choices=["ma_crossover", "bband", "multi_timeframe_bband"])
    parser.add_argument("--iteration", type=int, default=1, help="Iteration number for research artifacts")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--start", default="")
    parser.add_argument("--end", default="")
    parser.add_argument("--initial-capital", type=float, default=10000.0)
    parser.add_argument("--commission-rate", type=float, default=0.001)
    parser.add_argument("--position-size", type=float, default=1.0)
    parser.add_argument("--research-dir", default="research")
    parser.add_argument("--short-window", type=int)
    parser.add_argument("--long-window", type=int)
    parser.add_argument("--bband-period", type=int)
    parser.add_argument("--bband-std", type=float)
    parser.add_argument("--ma-period", type=int)
    parser.add_argument("--entry-threshold", type=float)
    parser.add_argument("--exit-threshold", type=float)
    parser.add_argument("--use-ma-confirm", action="store_true", default=None)
    parser.add_argument("--require-confirm", action="store_true", default=None)
    parser.add_argument("--param", action="append", default=[], help="Extra strategy param in KEY=VALUE format")
    return parser


def resolve_strategy_class(strategy_name: str):
    from strategies import BBandStrategy, MACrossoverStrategy, MultiTimeframeBBandStrategy

    mapping = {
        "ma_crossover": MACrossoverStrategy,
        "bband": BBandStrategy,
        "multi_timeframe_bband": MultiTimeframeBBandStrategy,
    }
    return mapping[strategy_name]


def main() -> None:
    parser = create_parser()
    args = parser.parse_args()

    from agents.backtest_runner_agent import BacktestConfig, create_backtest_runner
    from agents.strategy_evaluator_agent import create_strategy_evaluator

    strategy_params = collect_strategy_params(args, args.param)
    strategy_class = resolve_strategy_class(args.strategy)
    command = build_backtest_command(args, strategy_params)

    backtester = create_backtest_runner(str(PROJECT_ROOT / "data"))
    backtest_config = BacktestConfig(
        symbol=args.symbol,
        interval=args.interval,
        start_date=args.start or None,
        end_date=args.end or None,
        initial_capital=args.initial_capital,
        commission_rate=args.commission_rate,
        position_size=args.position_size,
    )
    report = backtester.run_backtest(
        strategy_name=args.strategy,
        strategy_class=strategy_class,
        strategy_params=strategy_params,
        config=backtest_config,
    )
    evaluation = create_strategy_evaluator().evaluate(report)

    writer = ResearchArtifactWriter(args.research_dir)
    writer.ensure_workspace()
    strategy_stub = build_strategy_stub(args.strategy, strategy_params, args.interval)
    writer.write_backtest_report(
        iteration=args.iteration,
        strategy_spec=strategy_stub,
        backtest_report=report,
        evaluation=evaluation,
        command=command,
        status="success",
        notes=list(getattr(evaluation, "weaknesses", []) or []),
    )
    writer.append_iteration_log(
        iteration=args.iteration,
        spec_version=f"{args.strategy}-iteration-{args.iteration}",
        code_status="external",
        backtest_status="success",
        total_return=report.total_return,
        max_drawdown=report.max_drawdown,
        strategy_recommendation=getattr(evaluation.result, "value", str(evaluation.result)),
        human_decision=None,
        next_action="human_checkpoint",
    )

    print(f"strategy: {args.strategy}")
    print(f"return_pct: {report.total_return:.2f}")
    print(f"max_drawdown_pct: {report.max_drawdown:.2f}")
    print(f"research_dir: {Path(args.research_dir).resolve()}")


if __name__ == "__main__":
    main()
