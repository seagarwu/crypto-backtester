#!/usr/bin/env python3
"""
Strategy Evaluator Agent - 策略評估 Agent

職責：
- 評估回測結果
- 判斷策略是否通過門檻
- 提供改進建議
"""

import os
import sys
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging

# 確保可以匯入模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm_manager import get_llm

# Agent 角色定義（避免循環導入）
from enum import Enum
from dataclasses import dataclass

class AgentRole(Enum):
    """Agent 角色定義"""
    MARKET_MONITOR = "market_monitor"
    RISK_MANAGER = "risk_manager"
    STRATEGY_DEVELOPER = "strategy_dev"
    BACKTESTER = "backtester"
    ENGINEER = "engineer"
    REPORTER = "reporter"

@dataclass
class AgentConfig:
    """Agent 配置"""
    role: AgentRole
    model: str = "minimax/minimax-m2.1"
    temperature: float = 0.7
    max_tokens: int = 2000
    system_prompt: str = ""

# Agent Prompt 模板
AGENT_PROMPTS = {
    AgentRole.BACKTESTER: """你是一個回測專家。

你的職責：
- 測試交易策略的歷史表現
- 計算關鍵指標（Sharpe, Drawdown, Win Rate）
- 提供改進建議""",
}

logger = logging.getLogger(__name__)


class EvaluationResult(Enum):
    """評估結果"""
    PASS = "pass"
    FAIL = "fail"
    NEEDS_IMPROVEMENT = "needs_improvement"


@dataclass
class EvaluationMetrics:
    """評估指標門檻"""
    min_sharpe: float = 1.0
    max_drawdown: float = 30.0  # %
    min_win_rate: float = 40.0  # %
    min_trades: int = 30
    min_total_return: float = 0.0  # %
    max_volatility: float = 50.0  # %


@dataclass
class StrategyEvaluation:
    """策略評估結果"""
    result: EvaluationResult
    score: float  # 0-100
    
    # 通過的檢查
    sharpe_passed: bool = False
    drawdown_passed: bool = False
    win_rate_passed: bool = False
    trades_passed: bool = False
    return_passed: bool = False
    
    # 評估意見
    summary: str = ""
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class StrategyEvaluatorAgent:
    """
    策略評估 Agent
    
    負責：
    1. 根據門檻評估策略表現
    2. 分析策略優缺點
    3. 提供改進建議
    """
    
    def __init__(
        self,
        model: str = "minimax/minimax-m2.1",
        metrics: EvaluationMetrics = None,
    ):
        self.model = model
        self.metrics = metrics or EvaluationMetrics()
        self.llm = None
        
        self.system_prompt = """你是一個專業的量化策略評估專家。

你的職責：
- 評估交易策略的歷史表現
- 識別策略的優點和缺點
- 提供具體的改進建議

請根據數據提供：
1. 策略評估結論
2. 優勢分析
3. 劣勢分析
4. 改進建議"""
    
    def _get_llm(self):
        """懒加载 LLM"""
        if self.llm is None:
            config = AgentConfig(
                role=AgentRole.BACKTESTER,
                model=self.model,
                system_prompt=self.system_prompt,
            )
            self.llm = get_llm(config)
        return self.llm
    
    def evaluate(
        self,
        backtest_report,
        metrics: Dict[str, Any] = None,
        target_metrics: Dict[str, float] = None,
    ) -> StrategyEvaluation:
        """
        評估策略
        
        Args:
            backtest_report: BacktestResult 物件
            metrics: 計算好的績效指標字典 (可選)
            target_metrics: 目標指標 (可選)
            
        Returns:
            StrategyEvaluation: 評估結果
        """
        # 如果有傳入 metrics 字典，直接使用
        if metrics is not None:
            # 從 metrics 字典獲取指標
            sharpe_ratio = metrics.get('sharpe_ratio', 0)
            max_drawdown = metrics.get('max_drawdown', 0)
            win_rate = metrics.get('win_rate', 0)
            total_return = metrics.get('total_return', 0)
            profit_factor = metrics.get('profit_factor', 0)
        else:
            # 從 backtest_report 獲取指標（向後兼容）
            sharpe_ratio = getattr(backtest_report, 'sharpe_ratio', 0)
            max_drawdown = getattr(backtest_report, 'max_drawdown', 0)
            win_rate = getattr(backtest_report, 'win_rate', 0)
            total_return = getattr(backtest_report, 'total_return', 0)
            profit_factor = getattr(backtest_report, 'profit_factor', 0)
        metrics = self.metrics
        if target_metrics:
            metrics = EvaluationMetrics(
                min_sharpe=target_metrics.get('sharpe', metrics.min_sharpe),
                max_drawdown=target_metrics.get('max_drawdown', metrics.max_drawdown),
                min_win_rate=target_metrics.get('win_rate', metrics.min_win_rate),
                min_trades=target_metrics.get('trades', metrics.min_trades),
                min_total_return=target_metrics.get('return', metrics.min_total_return),
            )
        
        # 檢查各項指標
        sharpe_passed = sharpe_ratio >= metrics.min_sharpe
        drawdown_passed = max_drawdown <= metrics.max_drawdown
        win_rate_passed = win_rate >= metrics.min_win_rate
        trades_passed = backtest_report.total_trades >= metrics.min_trades
        return_passed = total_return >= metrics.min_total_return
        
        # 計算分數
        score = self._calculate_score(
            backtest_report,
            sharpe_passed,
            drawdown_passed,
            win_rate_passed,
            trades_passed,
            return_passed,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
        )
        
        # 決定結果
        if all([sharpe_passed, drawdown_passed, win_rate_passed, return_passed]):
            result = EvaluationResult.PASS
        elif score >= 50:
            result = EvaluationResult.NEEDS_IMPROVEMENT
        else:
            result = EvaluationResult.FAIL
        
        # 生成意見
        strengths, weaknesses, recommendations = self._generate_feedback(
            backtest_report,
            sharpe_passed,
            drawdown_passed,
            win_rate_passed,
            trades_passed,
            return_passed,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            total_return=total_return,
            profit_factor=profit_factor,
        )
        
        summary = self._generate_summary(result, score, backtest_report)
        
        return StrategyEvaluation(
            result=result,
            score=score,
            sharpe_passed=sharpe_passed,
            drawdown_passed=drawdown_passed,
            win_rate_passed=win_rate_passed,
            trades_passed=trades_passed,
            return_passed=return_passed,
            summary=summary,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations,
        )
    
    def _calculate_score(
        self,
        report,
        sharpe_passed: bool,
        drawdown_passed: bool,
        win_rate_passed: bool,
        trades_passed: bool,
        return_passed: bool,
        sharpe_ratio: float = None,
        max_drawdown: float = None,
        win_rate: float = None,
    ) -> float:
        """計算綜合分數"""
        # 如果有傳入，直接使用；否則從 report 獲取
        if sharpe_ratio is None:
            sharpe_ratio = getattr(report, 'sharpe_ratio', 0)
        if max_drawdown is None:
            max_drawdown = getattr(report, 'max_drawdown', 0)
        if win_rate is None:
            win_rate = getattr(report, 'win_rate', 0)
        
        score = 0
        
        # Sharpe Ratio (25分)
        if sharpe_passed:
            score += 25
        else:
            score += max(0, 25 - (self.metrics.min_sharpe - sharpe_ratio) * 25)
        
        # Drawdown (25分)
        if drawdown_passed:
            score += 25
        else:
            score += max(0, 25 - (max_drawdown - self.metrics.max_drawdown) * 0.5)
        
        # Win Rate (20分)
        if win_rate_passed:
            score += 20
        else:
            score += max(0, 20 - (self.metrics.min_win_rate - win_rate) * 0.5)
        
        # 交易次數 (10分)
        if trades_passed:
            score += 10
        else:
            score += max(0, 10 * report.total_trades / self.metrics.min_trades)
        
        # 總收益 (20分)
        if return_passed:
            score += 20
        else:
            score += max(0, 20 * (report.total_return / self.metrics.min_total_return) 
                        if self.metrics.min_total_return > 0 else 0)
        
        return min(100, max(0, score))
    
    def _generate_feedback(
        self,
        report,
        sharpe_passed: bool,
        drawdown_passed: bool,
        win_rate_passed: bool,
        trades_passed: bool,
        return_passed: bool,
        sharpe_ratio: float = None,
        max_drawdown: float = None,
        win_rate: float = None,
        total_return: float = None,
        profit_factor: float = None,
    ) -> tuple:
        """生成回饋意見"""
        # 如果有傳入，直接使用；否則從 report 獲取
        if sharpe_ratio is None:
            sharpe_ratio = getattr(report, 'sharpe_ratio', 0)
        if max_drawdown is None:
            max_drawdown = getattr(report, 'max_drawdown', 0)
        if win_rate is None:
            win_rate = getattr(report, 'win_rate', 0)
        if total_return is None:
            total_return = getattr(report, 'total_return', 0)
        if profit_factor is None:
            profit_factor = getattr(report, 'profit_factor', 0)
        
        strengths = []
        weaknesses = []
        recommendations = []
        
        # 優勢
        if sharpe_passed:
            strengths.append(f"Sharpe Ratio 表現良好 ({sharpe_ratio:.2f})")
        if drawdown_passed:
            strengths.append(f"最大回撤可控 ({max_drawdown*100:.1f}%)")
        if win_rate_passed:
            strengths.append(f"勝率達標 ({win_rate*100:.1f}%)")
        if return_passed:
            strengths.append(f"總收益為正 ({total_return*100:.1f}%)")
        
        # 劣勢
        if not sharpe_passed:
            weaknesses.append(f"Sharpe Ratio 低 ({sharpe_ratio:.2f} < {self.metrics.min_sharpe})")
            recommendations.append(f"提高 Sharpe Ratio：優化進出场時機，或添加濾網條件")
        
        if not drawdown_passed:
            weaknesses.append(f"最大回撤過大 ({max_drawdown*100:.1f}% > {self.metrics.max_drawdown}%)")
            recommendations.append(f"降低回撤：減少倉位大小，或添加止損機制")
        
        if not win_rate_passed:
            weaknesses.append(f"勝率偏低 ({win_rate*100:.1f}% < {self.metrics.min_win_rate*100:.1f}%)")
            recommendations.append(f"提高勝率：優化進場信號，或調整止損止盈比例")
        
        if not trades_passed:
            weaknesses.append(f"交易次數不足 ({report.total_trades} < {self.metrics.min_trades})")
            recommendations.append(f"增加交易機會：放寬進場條件，或優化參數")
        
        if not return_passed and total_return < 0:
            weaknesses.append(f"總收益為負 ({total_return*100:.1f}%)")
            recommendations.append(f"檢視策略邏輯：可能需要完全重新設計")
        
        # 通用建議
        if profit_factor > 0:
            avg_loss = getattr(report, 'avg_loss', 0)
            if avg_loss != 0 and profit_factor < 1.5:
                recommendations.append(f"Profit Factor 較低 ({profit_factor:.2f})，建議調整盈虧比")
        
        volatility = getattr(report, 'volatility', 0)
        if volatility > self.metrics.max_volatility:
            recommendations.append(f"波動率過高 ({volatility:.1f}%)，考慮添加波動率濾網")
        
        return strengths, weaknesses, recommendations
    
    def _generate_summary(
        self,
        result: EvaluationResult,
        score: float,
        report,
    ) -> str:
        """生成評估摘要"""
        if result == EvaluationResult.PASS:
            return f"✅ 策略通過評估 (分數: {score:.0f}/100)"
        elif result == EvaluationResult.NEEDS_IMPROVEMENT:
            return f"⚠️ 策略需要改進 (分數: {score:.0f}/100)"
        else:
            return f"❌ 策略未通過評估 (分數: {score:.0f}/100)"
    
    def evaluate_with_llm(
        self,
        backtest_report,
        strategy_spec,
    ) -> str:
        """
        使用 LLM 生成深入評估
        
        Args:
            backtest_report: 回測報告
            strategy_spec: 策略規格
            
        Returns:
            str: LLM 生成的評估報告
        """
        llm = self._get_llm()
        
        prompt = f"""
請評估以下交易策略的表現：

## 策略名稱
{backtest_report.strategy_name}

## 策略描述
{strategy_spec.description if hasattr(strategy_spec, 'description') else 'N/A'}

## 回測結果
- 總收益率: {backtest_report.total_return:.2f}%
- 年化收益: {backtest_report.annual_return:.2f}%
- Sharpe Ratio: {backtest_report.sharpe_ratio:.2f}
- 最大回撤: {backtest_report.max_drawdown:.2f}%
- 波動率: {backtest_report.volatility:.2f}%
- 總交易次數: {backtest_report.total_trades}
- 勝率: {backtest_report.win_rate:.2f}%
- 盈利次數: {backtest_report.winning_trades}
- 虧損次數: {backtest_report.losing_trades}
- 平均盈利: {backtest_report.avg_win:.2f}
- 平均虧損: {backtest_report.avg_loss:.2f}
- Profit Factor: {backtest_report.profit_factor:.2f}

## 請提供
1. 策略整體評估
2. 主要優勢
3. 主要劣勢
4. 具體改進建議
"""
        
        try:
            response = llm.invoke(prompt)
            return response.content
        except Exception as e:
            logger.error(f"LLM 評估失敗: {e}")
            return "LLM 評估不可用"


# 便捷函數
def create_strategy_evaluator(
    model: str = "minimax/minimax-m2.1",
    metrics: EvaluationMetrics = None,
) -> StrategyEvaluatorAgent:
    """建立策略評估 Agent"""
    return StrategyEvaluatorAgent(model=model, metrics=metrics)


__all__ = [
    "StrategyEvaluatorAgent",
    "EvaluationResult",
    "EvaluationMetrics",
    "StrategyEvaluation",
    "create_strategy_evaluator",
]
