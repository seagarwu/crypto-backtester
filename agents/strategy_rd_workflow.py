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
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging
from pathlib import Path
import ast
import importlib.util
import inspect

# 確保可以匯入模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    
    def run(
        self,
        market_analysis: str = None,
        existing_strategies: List[str] = None,
        target_metrics: Dict[str, float] = None,
        initial_strategy: Optional[StrategySpec] = None,
        md_context: str = None,
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
            logger.info(f"   策略: {strategy.name}")
            logger.info(f"   指標: {', '.join(strategy.indicators)}")

            feedback = self._build_iteration_feedback(
                validation=self.iterations[-1]["validation"] if self.iterations else None,
                evaluation=self.iterations[-1]["evaluation"] if self.iterations else None,
            )

            logger.info("\n[2/5] Engineer Agent 生成/修正策略代碼...")
            if iteration == 1 or not self.current_code:
                code_result = self.developer.generate_strategy_code_structured(
                    strategy,
                    md_context=md_context,
                )
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
                })
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
                })
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
            self.iterations.append({
                'iteration': iteration,
                'strategy': strategy,
                'code_result': code_result,
                'validation': validation,
                'backtest_report': backtest_report,
                'evaluation': evaluation,
                'report': report,
            })
            
            self.current_report = report
            
            # 顯示簡短報告
            print(self.reporter.format_report_compact(report))
            
            # 檢查是否通過
            if evaluation.result == EvaluationResult.PASS:
                logger.info("\n✅ 策略通過評估！")
                break
            elif evaluation.result == EvaluationResult.FAIL:
                logger.info("\n❌ 策略未通過，嘗試優化...")
                if iteration >= self.config.max_iterations:
                    logger.warning("   已達最大迭代次數，停止優化")
                    break
            else:
                # NEEDS_IMPROVEMENT
                logger.info("\n⚠️ 策略需要改進，繼續優化...")
                if iteration >= self.config.max_iterations:
                    logger.warning("   已達最大迭代次數，停止優化")
                    break
        
        return self.current_report

    def _persist_code_artifact(self, filepath: Path, code: str) -> Path:
        """保存每輪生成的代碼 artifact。"""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(code, encoding="utf-8")
        return filepath

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
        try:
            ast.parse(code)
        except SyntaxError as exc:
            issues.append(f"Syntax error: {exc}")
            return CodeValidationResult(False, filepath=filepath, issues=issues)

        strategy_class = self._load_strategy_class(filepath)
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
    ) -> IterationFeedback:
        """整理 validation / evaluation 成結構化 feedback。"""
        feedback = IterationFeedback()
        if validation and validation.issues:
            feedback.validation_issues.extend(validation.issues)
            feedback.required_changes.extend(validation.issues)
        if evaluation is not None:
            feedback.performance_issues.extend(getattr(evaluation, "weaknesses", []))
            feedback.required_changes.extend(getattr(evaluation, "recommendations", []))
        return feedback

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
        if not self.iterations:
            return None
        
        # 找分數最高的
        best = max(self.iterations, key=lambda x: x['evaluation'].score)
        return best['strategy']
    
    def get_best_report(self) -> Optional[StrategyReport]:
        """獲取最佳報告"""
        if not self.iterations:
            return None
        
        best = max(self.iterations, key=lambda x: x['evaluation'].score)
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
    report = workflow.run()
    
    # 保存
    if args.save:
        workflow.save_report()
    
    # 等待人類審批
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
]
