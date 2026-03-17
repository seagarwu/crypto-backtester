#!/usr/bin/env python3
"""
Strategy R&D Workflow - 策略研發閉環

整合所有 Agent，實現自動化的策略研發流程：
1. 市場分析
2. 策略開發
3. 自動回測
4. 策略評估
5. 生成報告
6. 人類審批

使用方式:
    python -m agents.strategy_rd_workflow
"""

import os
import sys
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import logging
from pathlib import Path
import ast
import importlib.util
import inspect
import re
from enum import Enum

# 確保可以匯入模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from research_contracts import ResearchArtifactWriter

from agents.strategy_developer_agent import (
    StrategyDeveloperAgent,
    StrategySpec,
    EngineerCodeResult,
)
from agents.backtest_runner_agent import (
    BacktestRunnerAgent, 
    BacktestConfig, 
    BacktestReport,
    create_backtest_runner,
)
from agents.strategy_evaluator_agent import (
    StrategyEvaluatorAgent,
    EvaluationMetrics,
    EvaluationResult,
    create_strategy_evaluator,
)
from agents.reporter_agent import (
    ReporterAgent,
    StrategyReport,
    create_reporter,
)

logger = logging.getLogger(__name__)


@dataclass
class RDConfig:
    """研發配置"""
    # 回測配置
    symbol: str = "BTCUSDT"
    interval: str = "1h"
    start_date: str = "2023-01-01"
    end_date: str = "2024-12-31"
    initial_capital: float = 10000.0
    
    # 評估門檻
    min_sharpe: float = 1.0
    max_drawdown: float = 30.0
    min_win_rate: float = 40.0
    min_trades: int = 30
    min_total_return: float = 0.0
    
    # 迭代限制
    max_iterations: int = 5
    
    # 數據目錄
    data_dir: str = "data"
    
    # 報告輸出目錄
    report_dir: str = "reports"

    # Human-in-the-loop research artifacts
    research_dir: str = "research"


@dataclass
class CodeValidationResult:
    """生成代碼的驗證結果。"""
    passed: bool
    filepath: str = ""
    class_name: str = ""
    issues: List[str] = field(default_factory=list)
    smoke_metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IterationFeedback:
    """提供給 Engineer Agent 的結構化 feedback。"""
    bugs: List[str] = field(default_factory=list)
    performance_issues: List[str] = field(default_factory=list)
    required_changes: List[str] = field(default_factory=list)
    validation_issues: List[str] = field(default_factory=list)


class HumanDecisionAction(Enum):
    CONTINUE = "continue"
    REVISE = "revise"
    PIVOT = "pivot"
    STOP = "stop"
    ACCEPT = "accept"


@dataclass
class HumanDecision:
    """人類 checkpoint 決策。"""
    action: HumanDecisionAction
    rationale: str = ""
    next_focus: List[str] = field(default_factory=list)
    updated_strategy: Optional[StrategySpec] = None
    source: str = "human"


class StrategyRoute(Enum):
    KNOWN = "known"
    COMPOSABLE = "composable"
    NOVEL = "novel"


@dataclass
class RouteDecision:
    route: StrategyRoute
    strategy_family: str = ""
    reason: str = ""


class StrategyRDWorkflow:
    """
    策略研發閉環
    
    執行流程：
    1. 開發策略 → 2. 回測 → 3. 評估 → 4. 報告
                                       ↓
                              人類審批 → 通過就結束
                                    ↓
                              不通過就回到步驟 1
    """
    
    def __init__(self, config: RDConfig = None):
        self.config = config or RDConfig()
        
        # 初始化所有 Agents
        self.developer = StrategyDeveloperAgent()
        self.backtester = create_backtest_runner(self.config.data_dir)
        self.evaluator = create_strategy_evaluator(
            metrics=EvaluationMetrics(
                min_sharpe=self.config.min_sharpe,
                max_drawdown=self.config.max_drawdown,
                min_win_rate=self.config.min_win_rate,
                min_trades=self.config.min_trades,
                min_total_return=self.config.min_total_return,
            )
        )
        self.reporter = create_reporter()
        
        # 迭代歷史
        self.iterations: List[Dict[str, Any]] = []
        
        # 當前策略
        self.current_strategy: Optional[StrategySpec] = None
        self.current_report: Optional[StrategyReport] = None
        self.current_code: str = ""
        self.current_code_path: str = ""
        self.current_validated_code_path: str = ""
        self.route_decision: Optional[RouteDecision] = None
        self.pending_human_decision: Optional[HumanDecision] = None
        self.research_writer = ResearchArtifactWriter(self.config.research_dir)
        self.research_writer.ensure_workspace()
    
    def run(
        self,
        market_analysis: str = None,
        existing_strategies: List[str] = None,
        target_metrics: Dict[str, float] = None,
        initial_strategy: Optional[StrategySpec] = None,
        md_context: str = None,
        human_decision_provider: Optional[Callable[[Dict[str, Any]], HumanDecision]] = None,
    ) -> StrategyReport:
        """
        執行策略研發閉環
        
        Args:
            market_analysis: 市場分析 (可選)
            existing_strategies: 現有策略列表
            target_metrics: 目標指標
            
        Returns:
            StrategyReport: 最終報告
        """
        logger.info("=" * 60)
        logger.info("🚀 開始策略研發閉環")
        logger.info("=" * 60)
        
        artifact_dir = Path(self.config.report_dir) / "iterations"
        artifact_dir.mkdir(parents=True, exist_ok=True)

        for iteration in range(1, self.config.max_iterations + 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"📊 迭代 {iteration}/{self.config.max_iterations}")
            logger.info(f"{'='*60}")
            
            # 1. 開發/更新策略規格
            if iteration == 1 and initial_strategy is not None:
                logger.info("\n[1/4] 使用現有策略規格...")
                strategy = initial_strategy
            elif (
                self.pending_human_decision is not None
                and self.pending_human_decision.action is HumanDecisionAction.PIVOT
                and self.pending_human_decision.updated_strategy is not None
            ):
                logger.info("\n[1/4] 根據 human checkpoint pivot 到新策略規格...")
                strategy = self.pending_human_decision.updated_strategy
            elif iteration == 1:
                logger.info("\n[1/4] 開發新策略...")
                strategy = self.developer.develop_strategy(
                    market_analysis=market_analysis or "比特幣呈現上漲趨勢",
                    existing_strategies=existing_strategies,
                    target_metrics=target_metrics,
                )
            else:
                last_results = self.iterations[-1].get('backtest_report')
                if last_results is not None:
                    logger.info(f"\n[1/4] 根據回測結果優化策略...")
                    strategy = self.developer.optimize_strategy(
                        self.current_strategy,
                        last_results,
                    )
                else:
                    logger.info(f"\n[1/4] 保持策略規格，專注修正策略代碼...")
                    strategy = self.current_strategy
            
            self.current_strategy = strategy
            if iteration == 1:
                self.route_decision = self._classify_strategy(strategy)
            logger.info(f"   策略: {strategy.name}")
            logger.info(f"   指標: {', '.join(strategy.indicators)}")
            if self.route_decision:
                logger.info(
                    "   路由: %s (%s)",
                    self.route_decision.route.value,
                    self.route_decision.reason,
                )
            self.research_writer.write_strategy_spec(
                strategy_spec=strategy,
                iteration=iteration,
                market=self.config.symbol,
                timeframe=self.config.interval,
                acceptance_criteria=self._acceptance_criteria(),
                human_decision=self.pending_human_decision,
            )

            feedback = self._build_iteration_feedback(
                validation=self.iterations[-1]["validation"] if self.iterations else None,
                evaluation=self.iterations[-1]["evaluation"] if self.iterations else None,
                human_decision=self.pending_human_decision,
            )

            logger.info("\n[2/5] Engineer Agent 生成/修正策略代碼...")
            if iteration == 1 and self.route_decision and self.route_decision.route in (StrategyRoute.KNOWN, StrategyRoute.COMPOSABLE):
                code_result = self._build_deterministic_code_result(strategy, self.route_decision)
            elif iteration == 1 or not self.current_code:
                code_result = self.developer.generate_strategy_code_structured(
                    strategy,
                    md_context=md_context,
                )
            else:
                if self.route_decision and self.route_decision.route in (StrategyRoute.KNOWN, StrategyRoute.COMPOSABLE):
                    logger.info("   使用 deterministic route 重新生成代碼，不走自由修補")
                    code_result = self._build_deterministic_code_result(strategy, self.route_decision)
                else:
                    code_result = self.developer.revise_strategy_code(
                        strategy,
                        feedback=self._feedback_to_dict(feedback),
                        previous_code=self.current_code,
                        md_context=md_context,
                    )

            code_path = artifact_dir / f"iteration_{iteration:02d}_{strategy.name}.py"
            code_path = self._persist_code_artifact(code_path, code_result.code)
            raw_path = artifact_dir / f"iteration_{iteration:02d}_{strategy.name}.raw.txt"
            self._persist_raw_response_artifact(raw_path, code_result.raw_response)
            validation = self._validate_generated_code(
                filepath=str(code_path),
                strategy_spec=strategy,
                backtest_config=BacktestConfig(
                    symbol=self.config.symbol,
                    interval=self.config.interval,
                    start_date=self.config.start_date,
                    end_date=self.config.end_date,
                    initial_capital=self.config.initial_capital,
                ),
            )
            self.current_code = code_result.code
            self.current_code_path = str(code_path)
            self.research_writer.write_implementation_note(
                iteration=iteration,
                strategy_spec=strategy,
                code_result=code_result,
                validation=validation,
                code_path=str(code_path),
            )

            if not validation.passed:
                logger.warning("   代碼驗證失敗，進入下一輪修正")
                for issue in validation.issues:
                    logger.warning(f"   - {issue}")
                self.iterations.append({
                    "iteration": iteration,
                    "strategy": strategy,
                    "code_result": code_result,
                    "validation": validation,
                    "evaluation": None,
                    "report": None,
                    "human_decision": None,
                    "proposed_action": HumanDecisionAction.REVISE.value,
                })
                self._write_failed_iteration_artifacts(
                    iteration=iteration,
                    strategy=strategy,
                    validation=validation,
                    backtest_status="validation_failed",
                    next_action=HumanDecisionAction.REVISE.value,
                )
                if iteration >= self.config.max_iterations:
                    logger.warning("   已達最大迭代次數，停止優化")
                continue

            self.current_validated_code_path = validation.filepath

            # 3. 回測
            logger.info("\n[3/5] 執行回測...")
            backtest_config = BacktestConfig(
                symbol=self.config.symbol,
                interval=self.config.interval,
                start_date=self.config.start_date,
                end_date=self.config.end_date,
                initial_capital=self.config.initial_capital,
            )
            
            try:
                backtest_report = self.backtester.run_backtest(
                    strategy_name=strategy.name,
                    strategy_class=self._load_strategy_class(validation.filepath),
                    strategy_params=strategy.parameters,
                    config=backtest_config,
                )
            except Exception as e:
                logger.error(f"   回測失敗: {e}")
                validation.issues.append(f"Full backtest failed: {e}")
                self.iterations.append({
                    "iteration": iteration,
                    "strategy": strategy,
                    "code_result": code_result,
                    "validation": validation,
                    "evaluation": None,
                    "report": None,
                    "human_decision": None,
                    "proposed_action": HumanDecisionAction.REVISE.value,
                })
                self._write_failed_iteration_artifacts(
                    iteration=iteration,
                    strategy=strategy,
                    validation=validation,
                    backtest_status="failed",
                    next_action=HumanDecisionAction.REVISE.value,
                )
                if iteration >= self.config.max_iterations:
                    logger.warning("   已達最大迭代次數，停止優化")
                continue
            
            logger.info(f"   收益率: {backtest_report.total_return:.2f}%")
            logger.info(f"   Sharpe: {backtest_report.sharpe_ratio:.2f}")
            logger.info(f"   回撤:   {backtest_report.max_drawdown:.2f}%")
            logger.info(f"   勝率:   {backtest_report.win_rate:.2f}%")
            
            # 4. 評估
            logger.info("\n[4/5] 評估策略...")
            evaluation = self.evaluator.evaluate(
                backtest_report,
                target_metrics=target_metrics,
            )
            
            logger.info(f"   {evaluation.summary}")
            logger.info(f"   分數: {evaluation.score:.0f}/100")
            
            # 5. 報告
            logger.info("\n[5/5] 生成報告...")
            report = self.reporter.generate_report(
                market_analysis=market_analysis or "比特幣呈現上漲趨勢",
                strategy_spec=strategy,
                backtest_report=backtest_report,
                evaluation=evaluation,
                iteration=iteration,
            )
            
            # 保存這次迭代
            proposed_action = self._propose_next_action(evaluation)

            self.iterations.append({
                'iteration': iteration,
                'strategy': strategy,
                'code_result': code_result,
                'validation': validation,
                'backtest_report': backtest_report,
                'evaluation': evaluation,
                'report': report,
                'human_decision': None,
                'proposed_action': proposed_action.value,
            })

            self.current_report = report
            
            # 顯示簡短報告
            print(self.reporter.format_report_compact(report))
            
            decision_context = self._build_decision_context(
                iteration=iteration,
                strategy=strategy,
                validation=validation,
                backtest_report=backtest_report,
                evaluation=evaluation,
                report=report,
                proposed_action=proposed_action,
            )
            human_decision = self._resolve_human_decision(
                proposed_action=proposed_action,
                context=decision_context,
                provider=human_decision_provider,
            )
            self.iterations[-1]["human_decision"] = human_decision
            self.pending_human_decision = human_decision
            self._apply_human_decision(report, human_decision)
            self.research_writer.write_strategy_spec(
                strategy_spec=strategy,
                iteration=iteration,
                market=self.config.symbol,
                timeframe=self.config.interval,
                acceptance_criteria=self._acceptance_criteria(),
                human_decision=human_decision,
            )
            self.research_writer.write_backtest_report(
                iteration=iteration,
                strategy_spec=strategy,
                backtest_report=backtest_report,
                evaluation=evaluation,
                command=self._backtest_command_hint(strategy.name),
                status="success",
                notes=list(getattr(evaluation, "weaknesses", []) or []),
            )
            self.research_writer.append_iteration_log(
                iteration=iteration,
                spec_version=f"{strategy.name}-iteration-{iteration}",
                code_status="validated",
                backtest_status="success",
                total_return=backtest_report.total_return,
                max_drawdown=backtest_report.max_drawdown,
                strategy_recommendation=proposed_action.value,
                human_decision=human_decision,
                next_action=human_decision.action.value,
            )

            logger.info(
                "\n🧑 Human checkpoint: %s%s",
                human_decision.action.value,
                f" | {human_decision.rationale}" if human_decision.rationale else "",
            )

            if human_decision.action in (HumanDecisionAction.ACCEPT, HumanDecisionAction.STOP):
                logger.info("\n🛑 依 human decision 結束當前策略 loop")
                break

            if iteration >= self.config.max_iterations:
                logger.warning("   已達最大迭代次數，停止優化")
                break

            if human_decision.action is HumanDecisionAction.PIVOT:
                logger.info("\n🔀 下一輪將依 human decision pivot 新策略方向")
            elif human_decision.action is HumanDecisionAction.REVISE:
                logger.info("\n⚠️ 依 human decision 繼續修正策略")
            else:
                logger.info("\n🔁 依 human decision 繼續下一輪")

        return self.current_report

    def _persist_code_artifact(self, filepath: Path, code: str) -> Path:
        """保存每輪生成的代碼 artifact。"""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(code, encoding="utf-8")
        return filepath

    def _normalized_indicators(self, strategy_spec: StrategySpec) -> set[str]:
        normalized = set()
        for indicator in (strategy_spec.indicators or []):
            value = str(indicator).strip().strip("'\"").strip().lower()
            if value:
                normalized.add(value)
        return normalized

    def _classify_strategy(self, strategy_spec: StrategySpec) -> RouteDecision:
        indicators = self._normalized_indicators(strategy_spec)
        params = strategy_spec.parameters or {}
        known_indicators = {"ma", "ma20", "ma50", "ma60", "bband", "volume", "rsi", "macd", "breakout", "high", "low"}

        if {"bband", "volume"}.issubset(indicators) and "higher_timeframe" in params and "entry_timeframe" in params:
            return RouteDecision(
                route=StrategyRoute.KNOWN,
                strategy_family="multi_timeframe_bband_reversion",
                reason="Known multi-timeframe BBand pattern with explicit params",
            )
        if "bband" in indicators and "higher_timeframe" not in params and "entry_timeframe" not in params:
            return RouteDecision(
                route=StrategyRoute.KNOWN,
                strategy_family="bband_reversion",
                reason="Known single-timeframe BBand family",
            )
        if "ma" in indicators or {"ma20", "ma50"}.issubset(indicators):
            return RouteDecision(
                route=StrategyRoute.KNOWN,
                strategy_family="ma_crossover",
                reason="Known moving-average crossover family",
            )
        if indicators and indicators.issubset(known_indicators):
            return RouteDecision(
                route=StrategyRoute.COMPOSABLE,
                strategy_family="generic_rule_based",
                reason="Uses known indicators but novel composition",
            )
        return RouteDecision(
            route=StrategyRoute.NOVEL,
            strategy_family="novel",
            reason="Needs design review before code generation",
        )

    def _build_deterministic_code_result(
        self,
        strategy_spec: StrategySpec,
        route_decision: RouteDecision,
    ) -> EngineerCodeResult:
        if route_decision.strategy_family == "multi_timeframe_bband_reversion":
            code = self._generate_multi_timeframe_bband_code(strategy_spec)
        elif route_decision.strategy_family == "bband_reversion":
            code = self._generate_single_timeframe_bband_code(strategy_spec)
        elif route_decision.strategy_family == "ma_crossover":
            code = self._generate_ma_crossover_code(strategy_spec)
        else:
            code = self._generate_generic_rule_based_code(strategy_spec)

        return EngineerCodeResult(
            code=code,
            summary=f"Deterministic {route_decision.route.value} route for {route_decision.strategy_family}",
            assumptions=[route_decision.reason],
            raw_response=f"[deterministic_route]\nroute={route_decision.route.value}\nfamily={route_decision.strategy_family}\nreason={route_decision.reason}",
        )

    def _safe_class_name(self, strategy_name: str) -> str:
        class_name = re.sub(r"[^a-zA-Z0-9_]", "", strategy_name.title().replace(" ", "")) or "GeneratedStrategy"
        if not class_name.endswith("Strategy"):
            class_name += "Strategy"
        return class_name

    def _generate_multi_timeframe_bband_code(self, strategy_spec: StrategySpec) -> str:
        class_name = self._safe_class_name(strategy_spec.name)
        params = strategy_spec.parameters or {}
        bb_period = int(params.get("bb_period", 20))
        bb_std = float(params.get("bb_std", 2.0))
        volume_ma_period = int(params.get("volume_ma_period", 20))
        volume_multiplier = float(params.get("volume_multiplier", 2.0))
        stop_loss_pct = float(params.get("stop_loss_pct", 0.03))
        higher_timeframe = str(params.get("higher_timeframe", "4h"))
        entry_timeframe = str(params.get("entry_timeframe", strategy_spec.timeframe or "1h"))
        strategy_name = strategy_spec.name.replace('"', '\\"')

        return f'''from strategies.base import BaseStrategy, SignalType
import pandas as pd


class {class_name}(BaseStrategy):
    def __init__(
        self,
        bb_period: int = {bb_period},
        bb_std: float = {bb_std},
        volume_ma_period: int = {volume_ma_period},
        volume_multiplier: float = {volume_multiplier},
        stop_loss_pct: float = {stop_loss_pct},
        higher_timeframe: str = "{higher_timeframe}",
        entry_timeframe: str = "{entry_timeframe}",
        name: str = "{strategy_name}",
    ):
        super().__init__(name=name)
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.volume_ma_period = volume_ma_period
        self.volume_multiplier = volume_multiplier
        self.stop_loss_pct = stop_loss_pct
        self.higher_timeframe = higher_timeframe
        self.entry_timeframe = entry_timeframe
        self.required_indicators = [
            f"BBand_{{bb_period}}_{{bb_std}}",
            f"Volume_MA_{{volume_ma_period}}",
        ]

    def calculate_signals(self, data: pd.DataFrame, indicators: dict) -> dict:
        row = data.iloc[-1]
        long_setup = bool(row.get("higher_long_setup", False))
        touch_lower = bool(row.get("touch_lower", False))
        touch_upper = bool(row.get("touch_upper", False))
        volume_ok = bool(row.get("volume_ok", False))
        in_position = bool(row.get("in_position", False))
        stop_loss_hit = bool(row.get("stop_loss_hit", False))
        if in_position and (touch_upper or stop_loss_hit):
            return {{"signal": SignalType.SELL, "strength": 1.0}}
        if (not in_position) and long_setup and touch_lower and volume_ok:
            return {{"signal": SignalType.BUY, "strength": 1.0}}
        return {{"signal": SignalType.HOLD, "strength": 0.0}}

    def _calc_bbands(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["bb_middle"] = df["close"].rolling(window=self.bb_period).mean()
        rolling_std = df["close"].rolling(window=self.bb_period).std()
        df["bb_upper"] = df["bb_middle"] + (rolling_std * self.bb_std)
        df["bb_lower"] = df["bb_middle"] - (rolling_std * self.bb_std)
        return df

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)
        higher_df = (
            df.set_index("datetime")
            .resample(str(self.higher_timeframe).lower())
            .agg({{"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}})
            .dropna()
            .reset_index()
        )
        higher_df = self._calc_bbands(higher_df)
        higher_df["higher_long_setup"] = higher_df["low"] <= higher_df["bb_lower"]
        higher_df = higher_df[["datetime", "higher_long_setup"]]
        df = self._calc_bbands(df)
        df["volume_ma"] = df["volume"].rolling(window=self.volume_ma_period).mean()
        df["volume_ok"] = df["volume"] >= (df["volume_ma"] * self.volume_multiplier)
        df["touch_lower"] = df["low"] <= df["bb_lower"]
        df["touch_upper"] = df["high"] >= df["bb_upper"]
        df = pd.merge_asof(
            df.sort_values("datetime"),
            higher_df.sort_values("datetime"),
            on="datetime",
            direction="backward",
        )
        df["higher_long_setup"] = df["higher_long_setup"].fillna(False)
        in_position = False
        entry_price = None
        signals = []
        for _, row in df.iterrows():
            stop_loss_hit = False
            if in_position and entry_price is not None:
                stop_price = entry_price * (1.0 - self.stop_loss_pct)
                stop_loss_hit = row["low"] <= stop_price
            signal = SignalType.HOLD
            if in_position and (row["touch_upper"] or stop_loss_hit):
                signal = SignalType.SELL
                in_position = False
                entry_price = None
            elif (not in_position) and row["higher_long_setup"] and row["touch_lower"] and row["volume_ok"]:
                signal = SignalType.BUY
                in_position = True
                entry_price = row["close"]
            signals.append(signal)
        df["signal"] = signals
        return df
'''

    def _generate_single_timeframe_bband_code(self, strategy_spec: StrategySpec) -> str:
        class_name = self._safe_class_name(strategy_spec.name)
        params = strategy_spec.parameters or {}
        period = int(params.get("bband_period", params.get("bb_period", 20)))
        std = float(params.get("bband_std", params.get("bb_std", 2.0)))
        entry_threshold = float(params.get("entry_threshold", 0.1))
        exit_threshold = float(params.get("exit_threshold", 0.9))
        strategy_name = strategy_spec.name.replace('"', '\\"')

        return f'''from strategies.base import BaseStrategy, SignalType
import pandas as pd


class {class_name}(BaseStrategy):
    def __init__(
        self,
        bband_period: int = {period},
        bband_std: float = {std},
        entry_threshold: float = {entry_threshold},
        exit_threshold: float = {exit_threshold},
        name: str = "{strategy_name}",
    ):
        super().__init__(name=name)
        self.bband_period = bband_period
        self.bband_std = bband_std
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.required_indicators = [f"BBand_{{bband_period}}_{{bband_std}}"]

    def calculate_signals(self, data: pd.DataFrame, indicators: dict) -> dict:
        row = data.iloc[-1]
        if row.get("bb_position", 0.5) <= self.entry_threshold:
            return {{"signal": SignalType.BUY, "strength": 1.0}}
        if row.get("bb_position", 0.5) >= self.exit_threshold:
            return {{"signal": SignalType.SELL, "strength": 1.0}}
        return {{"signal": SignalType.HOLD, "strength": 0.0}}

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df["bb_middle"] = df["close"].rolling(window=self.bband_period).mean()
        rolling_std = df["close"].rolling(window=self.bband_period).std()
        df["bb_upper"] = df["bb_middle"] + rolling_std * self.bband_std
        df["bb_lower"] = df["bb_middle"] - rolling_std * self.bband_std
        bb_range = (df["bb_upper"] - df["bb_lower"]).replace(0, pd.NA)
        df["bb_position"] = ((df["close"] - df["bb_lower"]) / bb_range).fillna(0.5)
        df["signal"] = SignalType.HOLD
        in_position = False
        for idx in range(len(df)):
            if not in_position and df.loc[df.index[idx], "bb_position"] <= self.entry_threshold:
                df.loc[df.index[idx], "signal"] = SignalType.BUY
                in_position = True
            elif in_position and df.loc[df.index[idx], "bb_position"] >= self.exit_threshold:
                df.loc[df.index[idx], "signal"] = SignalType.SELL
                in_position = False
        return df
'''

    def _generate_ma_crossover_code(self, strategy_spec: StrategySpec) -> str:
        class_name = self._safe_class_name(strategy_spec.name)
        params = strategy_spec.parameters or {}
        short_window = int(params.get("short_window", params.get("fast_ma", 20)))
        long_window = int(params.get("long_window", params.get("slow_ma", 50)))
        strategy_name = strategy_spec.name.replace('"', '\\"')
        return f'''from strategies.base import BaseStrategy, SignalType
import pandas as pd


class {class_name}(BaseStrategy):
    def __init__(self, short_window: int = {short_window}, long_window: int = {long_window}, name: str = "{strategy_name}"):
        super().__init__(name=name)
        self.short_window = short_window
        self.long_window = long_window
        self.required_indicators = [f"MA_{{short_window}}", f"MA_{{long_window}}"]

    def calculate_signals(self, data: pd.DataFrame, indicators: dict) -> dict:
        row = data.iloc[-1]
        prev = data.iloc[-2] if len(data) > 1 else row
        if prev.get("ma_short", 0) <= prev.get("ma_long", 0) and row.get("ma_short", 0) > row.get("ma_long", 0):
            return {{"signal": SignalType.BUY, "strength": 1.0}}
        if prev.get("ma_short", 0) >= prev.get("ma_long", 0) and row.get("ma_short", 0) < row.get("ma_long", 0):
            return {{"signal": SignalType.SELL, "strength": 1.0}}
        return {{"signal": SignalType.HOLD, "strength": 0.0}}

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df["ma_short"] = df["close"].rolling(window=self.short_window).mean()
        df["ma_long"] = df["close"].rolling(window=self.long_window).mean()
        df["signal"] = SignalType.HOLD
        for idx in range(1, len(df)):
            prev = df.iloc[idx - 1]
            row = df.iloc[idx]
            if pd.isna(prev["ma_short"]) or pd.isna(prev["ma_long"]) or pd.isna(row["ma_short"]) or pd.isna(row["ma_long"]):
                continue
            if prev["ma_short"] <= prev["ma_long"] and row["ma_short"] > row["ma_long"]:
                df.loc[df.index[idx], "signal"] = SignalType.BUY
            elif prev["ma_short"] >= prev["ma_long"] and row["ma_short"] < row["ma_long"]:
                df.loc[df.index[idx], "signal"] = SignalType.SELL
        return df
'''

    def _generate_generic_rule_based_code(self, strategy_spec: StrategySpec) -> str:
        class_name = self._safe_class_name(strategy_spec.name)
        strategy_name = strategy_spec.name.replace('"', '\\"')
        indicators = ", ".join(sorted(self._normalized_indicators(strategy_spec)))
        return f'''from strategies.base import BaseStrategy, SignalType
import pandas as pd


class {class_name}(BaseStrategy):
    def __init__(self, name: str = "{strategy_name}"):
        super().__init__(name=name)
        self.required_indicators = []

    def calculate_signals(self, data: pd.DataFrame, indicators: dict) -> dict:
        return {{"signal": SignalType.HOLD, "strength": 0.0}}

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        if "datetime" not in df.columns:
            df["datetime"] = df.index
        df["signal"] = SignalType.HOLD
        return df
'''

    def _persist_raw_response_artifact(self, filepath: Path, raw_response: str) -> Path:
        """保存每輪原始 LLM 回應，便於比對模型輸出與清洗後代碼。"""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(raw_response or "", encoding="utf-8")
        return filepath

    def _load_strategy_class(self, filepath: str):
        """從生成檔案中載入策略類別。"""
        spec = importlib.util.spec_from_file_location(Path(filepath).stem, filepath)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        from strategies.base import BaseStrategy

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, BaseStrategy) and attr is not BaseStrategy:
                return attr
        return None

    def _validate_generated_code(
        self,
        filepath: str,
        strategy_spec: StrategySpec,
        backtest_config: BacktestConfig,
    ) -> CodeValidationResult:
        """驗證生成代碼，包含語法、匯入、實例化與 smoke backtest。"""
        issues: List[str] = []

        code = Path(filepath).read_text(encoding="utf-8")
        if not code.strip():
            issues.append("No code generated")
            return CodeValidationResult(False, filepath=filepath, issues=issues)

        forbidden_imports = {
            "pandas_ta": "Forbidden dependency 'pandas_ta' is not available in this project",
            "talib": "Forbidden dependency 'talib' is not available in this project",
            "backtrader": "Forbidden dependency 'backtrader' is not available in this project",
            "vectorbt": "Forbidden dependency 'vectorbt' is not available in this project",
        }
        for module_name, message in forbidden_imports.items():
            if f"import {module_name}" in code or f"from {module_name} " in code:
                issues.append(message)
        if issues:
            return CodeValidationResult(False, filepath=filepath, issues=issues)

        try:
            ast.parse(code)
        except SyntaxError as exc:
            issues.append(f"Syntax error: {exc}")
            return CodeValidationResult(False, filepath=filepath, issues=issues)

        try:
            strategy_class = self._load_strategy_class(filepath)
        except ModuleNotFoundError as exc:
            issues.append(f"Strategy import failed: missing dependency '{exc.name}'")
            return CodeValidationResult(False, filepath=filepath, issues=issues)
        except Exception as exc:
            issues.append(f"Strategy import failed: {exc}")
            return CodeValidationResult(False, filepath=filepath, issues=issues)
        if strategy_class is None:
            issues.append("No BaseStrategy subclass found")
            return CodeValidationResult(False, filepath=filepath, issues=issues)

        try:
            strategy = self._instantiate_strategy(strategy_class, strategy_spec.parameters)
        except Exception as exc:
            issues.append(f"Strategy instantiation failed: {exc}")
            return CodeValidationResult(False, filepath=filepath, class_name=strategy_class.__name__, issues=issues)

        try:
            sample_data = self.backtester.load_data(
                backtest_config.symbol,
                backtest_config.interval,
                backtest_config.start_date,
                backtest_config.end_date,
            ).head(300).copy()
            signals = strategy.generate_signals(sample_data)
            if "signal" not in signals.columns:
                issues.append("Generated signals missing 'signal' column")
                return CodeValidationResult(False, filepath=filepath, class_name=strategy_class.__name__, issues=issues)

            engine = create_backtest_runner(self.config.data_dir)
            smoke_report = engine.run_backtest(
                strategy_name=strategy_spec.name,
                strategy_class=strategy_class,
                strategy_params=strategy_spec.parameters,
                config=BacktestConfig(
                    symbol=backtest_config.symbol,
                    interval=backtest_config.interval,
                    start_date=backtest_config.start_date,
                    end_date=backtest_config.end_date,
                    initial_capital=min(backtest_config.initial_capital, 1000.0),
                ),
            )
            smoke_metrics = {
                "total_return": smoke_report.total_return,
                "sharpe_ratio": smoke_report.sharpe_ratio,
                "max_drawdown": smoke_report.max_drawdown,
                "total_trades": smoke_report.total_trades,
            }
        except Exception as exc:
            issues.append(f"Smoke backtest failed: {exc}")
            return CodeValidationResult(False, filepath=filepath, class_name=strategy_class.__name__, issues=issues)

        return CodeValidationResult(
            passed=True,
            filepath=filepath,
            class_name=strategy_class.__name__,
            issues=[],
            smoke_metrics=smoke_metrics,
        )

    def _instantiate_strategy(self, strategy_class, parameters: Dict[str, Any]):
        """根據 __init__ 簽名建立策略實例。"""
        parameters = parameters or {}
        sig = inspect.signature(strategy_class.__init__)
        accepted = {}
        for name, param in sig.parameters.items():
            if name == "self":
                continue
            if param.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY):
                if name in parameters:
                    accepted[name] = parameters[name]
        return strategy_class(**accepted)

    def _build_iteration_feedback(
        self,
        validation: Optional[CodeValidationResult],
        evaluation,
        human_decision: Optional[HumanDecision] = None,
    ) -> IterationFeedback:
        """整理 validation / evaluation 成結構化 feedback。"""
        feedback = IterationFeedback()
        if validation and validation.issues:
            feedback.validation_issues.extend(validation.issues)
            feedback.required_changes.extend(validation.issues)
        if evaluation is not None:
            feedback.performance_issues.extend(getattr(evaluation, "weaknesses", []))
            feedback.required_changes.extend(getattr(evaluation, "recommendations", []))
        if human_decision is not None:
            if human_decision.rationale:
                feedback.required_changes.append(f"Human decision: {human_decision.rationale}")
            if human_decision.next_focus:
                feedback.required_changes.extend(
                    [f"Human priority: {item}" for item in human_decision.next_focus]
                )
        return feedback

    def _acceptance_criteria(self) -> List[str]:
        return [
            f"Return > {self.config.min_total_return:.2f}%",
            f"MDD < {self.config.max_drawdown:.2f}%",
            f"Sharpe > {self.config.min_sharpe:.2f}",
            f"Win rate > {self.config.min_win_rate:.2f}%",
            f"Trades >= {self.config.min_trades}",
        ]

    def _backtest_command_hint(self, strategy_name: str) -> str:
        return (
            f"workflow.run_backtest strategy={strategy_name} "
            f"symbol={self.config.symbol} interval={self.config.interval} "
            f"start={self.config.start_date} end={self.config.end_date}"
        )

    def _write_failed_iteration_artifacts(
        self,
        iteration: int,
        strategy: StrategySpec,
        validation: CodeValidationResult,
        backtest_status: str,
        next_action: str,
    ) -> None:
        self.research_writer.write_backtest_report(
            iteration=iteration,
            strategy_spec=strategy,
            backtest_report=None,
            evaluation=None,
            command=self._backtest_command_hint(strategy.name),
            status=backtest_status,
            notes=list(validation.issues or []),
        )
        self.research_writer.append_iteration_log(
            iteration=iteration,
            spec_version=f"{strategy.name}-iteration-{iteration}",
            code_status="validation_failed" if not validation.passed else "validated",
            backtest_status=backtest_status,
            total_return=None,
            max_drawdown=None,
            strategy_recommendation=HumanDecisionAction.REVISE.value,
            human_decision=None,
            next_action=next_action,
        )

    def _propose_next_action(self, evaluation) -> HumanDecisionAction:
        if evaluation.result == EvaluationResult.PASS:
            return HumanDecisionAction.ACCEPT
        if evaluation.result == EvaluationResult.FAIL:
            return HumanDecisionAction.REVISE
        return HumanDecisionAction.CONTINUE

    def _build_decision_context(
        self,
        iteration: int,
        strategy: StrategySpec,
        validation: CodeValidationResult,
        backtest_report: BacktestReport,
        evaluation,
        report: StrategyReport,
        proposed_action: HumanDecisionAction,
    ) -> Dict[str, Any]:
        return {
            "iteration": iteration,
            "strategy": strategy,
            "validation": validation,
            "backtest_report": backtest_report,
            "evaluation": evaluation,
            "report": report,
            "proposed_action": proposed_action,
        }

    def _resolve_human_decision(
        self,
        proposed_action: HumanDecisionAction,
        context: Dict[str, Any],
        provider: Optional[Callable[[Dict[str, Any]], HumanDecision]],
    ) -> HumanDecision:
        if provider is None:
            return HumanDecision(
                action=proposed_action,
                rationale="No explicit human override; follow workflow default",
                source="workflow-default",
            )

        decision = provider(context)
        return self._normalize_human_decision(decision, proposed_action)

    def _normalize_human_decision(
        self,
        decision: Any,
        default_action: HumanDecisionAction,
    ) -> HumanDecision:
        if isinstance(decision, HumanDecision):
            return decision
        if isinstance(decision, HumanDecisionAction):
            return HumanDecision(action=decision)
        if isinstance(decision, str):
            return HumanDecision(action=HumanDecisionAction(decision.strip().lower()))
        if isinstance(decision, dict):
            action = decision.get("action", default_action.value)
            updated_strategy = decision.get("updated_strategy")
            if isinstance(action, HumanDecisionAction):
                normalized_action = action
            else:
                normalized_action = HumanDecisionAction(str(action).strip().lower())
            return HumanDecision(
                action=normalized_action,
                rationale=str(decision.get("rationale", "")),
                next_focus=list(decision.get("next_focus", []) or []),
                updated_strategy=updated_strategy if isinstance(updated_strategy, StrategySpec) else None,
                source=str(decision.get("source", "human")),
            )

        raise TypeError(f"Unsupported human decision type: {type(decision)!r}")

    def _apply_human_decision(
        self,
        report: StrategyReport,
        decision: HumanDecision,
    ) -> None:
        if decision.action is HumanDecisionAction.ACCEPT:
            report.approved = True
        elif decision.action is HumanDecisionAction.STOP:
            report.approved = False
        report.approval_notes = decision.rationale

    def _feedback_to_dict(self, feedback: IterationFeedback) -> Dict[str, Any]:
        return {
            "bugs": feedback.bugs,
            "performance_issues": feedback.performance_issues,
            "required_changes": feedback.required_changes,
            "validation_issues": feedback.validation_issues,
        }
    
    def approve_strategy(self, notes: str = "") -> None:
        """
        批准當前策略
        
        Args:
            notes: 批准備註
        """
        if self.current_report:
            self.current_report.approved = True
            self.current_report.approval_notes = notes
            self.pending_human_decision = HumanDecision(
                action=HumanDecisionAction.ACCEPT,
                rationale=notes,
            )
            logger.info(f"\n✅ 策略已批准: {notes}")
    
    def reject_strategy(self, reason: str = "") -> None:
        """
        拒絕當前策略
        
        Args:
            reason: 拒絕原因
        """
        if self.current_report:
            self.current_report.approved = False
            self.current_report.approval_notes = reason
            self.pending_human_decision = HumanDecision(
                action=HumanDecisionAction.STOP,
                rationale=reason,
            )
            logger.info(f"\n❌ 策略已拒絕: {reason}")
    
    def save_report(self, format: str = "markdown") -> str:
        """
        保存最終報告
        
        Args:
            format: 格式 (markdown/json)
            
        Returns:
            str: 保存的路徑
        """
        if self.current_report:
            filepath = self.reporter.save_report(
                self.current_report,
                output_dir=self.config.report_dir,
                format=format,
            )
            logger.info(f"\n📄 報告已保存: {filepath}")
            return filepath
        return ""
    
    def get_best_strategy(self) -> Optional[StrategySpec]:
        """獲取最佳策略"""
        scored_iterations = [item for item in self.iterations if item.get("evaluation") is not None]
        if not scored_iterations:
            return None
        
        # 找分數最高的
        best = max(scored_iterations, key=lambda x: x['evaluation'].score)
        return best['strategy']
    
    def get_best_report(self) -> Optional[StrategyReport]:
        """獲取最佳報告"""
        scored_iterations = [item for item in self.iterations if item.get("evaluation") is not None]
        if not scored_iterations:
            return None
        
        best = max(scored_iterations, key=lambda x: x['evaluation'].score)
        return best['report']


# ==================== 命令列介面 ====================

def main():
    """主入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="策略研發閉環")
    parser.add_argument("--symbol", default="BTCUSDT", help="交易對")
    parser.add_argument("--interval", default="1h", help="時間框架")
    parser.add_argument("--start", default="2023-01-01", help="開始日期")
    parser.add_argument("--end", default="2024-12-31", help="結束日期")
    parser.add_argument("--capital", type=float, default=10000, help="初始資金")
    parser.add_argument("--iterations", type=int, default=5, help="最大迭代次數")
    parser.add_argument("--min-sharpe", type=float, default=1.0, help="最小 Sharpe")
    parser.add_argument("--max-dd", type=float, default=30.0, help="最大回撤%")
    parser.add_argument("--min-winrate", type=float, default=40.0, help="最小勝率%")
    parser.add_argument("--save", action="store_true", help="保存報告")
    
    args = parser.parse_args()
    
    # 配置
    config = RDConfig(
        symbol=args.symbol,
        interval=args.interval,
        start_date=args.start,
        end_date=args.end,
        initial_capital=args.capital,
        max_iterations=args.iterations,
        min_sharpe=args.min_sharpe,
        max_drawdown=args.max_dd,
        min_win_rate=args.min_winrate,
    )
    
    # 執行
    workflow = StrategyRDWorkflow(config)
    
    def prompt_human_checkpoint(context: Dict[str, Any]) -> HumanDecision:
        report = context["report"]
        proposed_action = context["proposed_action"]

        print("\n" + "=" * 60)
        print("Human checkpoint")
        print("=" * 60)
        print(f"策略: {report.strategy_name}")
        print(f"收益率: {report.total_return:.2f}%")
        print(f"Sharpe: {report.sharpe_ratio:.2f}")
        print(f"回撤: {report.max_drawdown:.2f}%")
        print(f"勝率: {report.win_rate:.2f}%")
        print(f"Agent 建議: {proposed_action.value}")
        print("可選動作: accept / continue / revise / pivot / stop")

        while True:
            action_raw = input("> action: ").strip().lower() or proposed_action.value
            try:
                action = HumanDecisionAction(action_raw)
                break
            except ValueError:
                print("請輸入 accept / continue / revise / pivot / stop")

        rationale = input("> rationale: ").strip()
        next_focus_raw = input("> next focus (comma separated, optional): ").strip()
        next_focus = [item.strip() for item in next_focus_raw.split(",") if item.strip()]
        return HumanDecision(action=action, rationale=rationale, next_focus=next_focus)

    report = workflow.run(human_decision_provider=prompt_human_checkpoint)
    
    # 保存
    if args.save:
        workflow.save_report()
    
    # 最終確認
    print("\n" + "=" * 60)
    print("請輸入決定:")
    print("  approve <備註> - 批准策略")
    print("  reject <原因> - 拒絕策略")
    print("  quit - 退出")
    print("=" * 60)
    
    while True:
        try:
            cmd = input("\n> ").strip()
            if not cmd:
                continue
            
            parts = cmd.split(None, 1)
            action = parts[0].lower()
            note = parts[1] if len(parts) > 1 else ""
            
            if action == "approve":
                workflow.approve_strategy(note)
                print("\n✅ 策略已批准！")
                print(f"\n最終報告:\n{workflow.reporter.format_report_markdown(report)}")
                break
            elif action == "reject":
                workflow.reject_strategy(note)
                print("\n❌ 策略已拒絕")
                break
            elif action == "quit":
                break
            else:
                print("未知命令")
                
        except (KeyboardInterrupt, EOFError):
            break
    
    print("\n👋 再見！")


if __name__ == "__main__":
    main()


__all__ = [
    "StrategyRDWorkflow",
    "RDConfig",
    "HumanDecision",
    "HumanDecisionAction",
]
