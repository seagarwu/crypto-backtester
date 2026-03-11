#!/usr/bin/env python3
"""
Reporter Agent - 彙報 Agent

職責：
- 彙總所有分析結果
- 生成人類可讀的報告
- 突出關鍵決策點
"""

import os
import sys
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
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
    model: str = "minimax/minimax-m2.5"
    temperature: float = 0.7
    max_tokens: int = 2000
    system_prompt: str = ""

# Agent Prompt 模板
AGENT_PROMPTS = {
    AgentRole.REPORTER: """你是一個投資組合經理助手。

你的職責：
- 彙總各Agent的分析結果
- 生成人類可讀的報告
- 突出關鍵決策點""",
}

logger = logging.getLogger(__name__)


@dataclass
class ReportSection:
    """報告章節"""
    title: str
    content: str
    priority: int = 1  # 1=高, 2=中, 3=低


@dataclass
class StrategyReport:
    """策略研發報告"""
    # 基本資訊
    strategy_name: str
    strategy_description: str
    created_at: datetime = field(default_factory=datetime.now)
    
    # 市場分析
    market_analysis: str = ""
    
    # 策略規格
    indicators: List[str] = field(default_factory=list)
    entry_rules: str = ""
    exit_rules: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # 回測結果
    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    
    # 評估結果
    evaluation_passed: bool = False
    evaluation_score: float = 0.0
    evaluation_summary: str = ""
    
    # 建議
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    # 最終決定
    approved: bool = False
    approval_notes: str = ""


class ReporterAgent:
    """
    彙報 Agent
    
    負責：
    1. 彙總各 Agent 的分析結果
    2. 生成結構化報告
    3. 格式化輸出
    """
    
    def __init__(
        self,
        model: str = "minimax/minimax-m2.5",
    ):
        self.model = model
        self.llm = None
        
        self.system_prompt = AGENT_PROMPTS.get(
            AgentRole.REPORTER,
            """你是一個投資組合經理助手。

你的職責：
- 彙總各Agent的分析結果
- 生成人類可讀的報告
- 突出關鍵決策點

請生成：
1. 執行摘要
2. 詳細分析
3. 建議行動"""
        )
    
    def _get_llm(self):
        """懒加载 LLM"""
        if self.llm is None:
            config = AgentConfig(
                role=AgentRole.REPORTER,
                model=self.model,
                system_prompt=self.system_prompt,
            )
            self.llm = get_llm(config)
        return self.llm
    
    def generate_report(
        self,
        market_analysis: str,
        strategy_spec,
        backtest_report,
        evaluation,
        iteration: int = 1,
    ) -> StrategyReport:
        """
        生成策略研發報告
        
        Args:
            market_analysis: 市場分析
            strategy_spec: 策略規格
            backtest_report: 回測報告
            evaluation: 評估結果
            iteration: 迭代次數
            
        Returns:
            StrategyReport: 策略報告
        """
        # 構建基本報告
        report = StrategyReport(
            strategy_name=strategy_spec.name,
            strategy_description=strategy_spec.description,
            market_analysis=market_analysis,
            indicators=strategy_spec.indicators,
            entry_rules=strategy_spec.entry_rules,
            exit_rules=strategy_spec.exit_rules,
            parameters=strategy_spec.parameters,
            
            total_return=backtest_report.total_return,
            sharpe_ratio=backtest_report.sharpe_ratio,
            max_drawdown=backtest_report.max_drawdown,
            win_rate=backtest_report.win_rate,
            total_trades=backtest_report.total_trades,
            
            evaluation_passed=evaluation.result.value == "pass",
            evaluation_score=evaluation.score,
            evaluation_summary=evaluation.summary,
            
            strengths=evaluation.strengths,
            weaknesses=evaluation.weaknesses,
            recommendations=evaluation.recommendations,
        )
        
        return report
    
    def format_report_markdown(self, report: StrategyReport) -> str:
        """
        格式化報告為 Markdown
        
        Args:
            report: 策略報告
            
        Returns:
            str: Markdown 格式報告
        """
        # 決定狀態emoji
        if report.evaluation_passed:
            status_emoji = "✅"
            status_text = "通過"
        else:
            status_emoji = "❌"
            status_text = "未通過"
        
        md = f"""# 策略研發報告

## 基本資訊

| 項目 | 值 |
|------|-----|
| 策略名稱 | {report.strategy_name} |
| 描述 | {report.strategy_description} |
| 創建時間 | {report.created_at.strftime('%Y-%m-%d %H:%M:%S')} |
| 評估狀態 | {status_emoji} {status_text} |

---

## 市場分析

{report.market_analysis or '無'}

---

## 策略規格

### 技術指標
{', '.join(report.indicators) if report.indicators else '無'}

### 進場規則
{report.entry_rules or '無'}

### 出場規則
{report.exit_rules or '無'}

### 參數
```json
{json.dumps(report.parameters, indent=2)}
```

---

## 回測結果

| 指標 | 值 | 評估 |
|------|-----|------|
| 總收益率 | {report.total_return:.2f}% | {'✅' if report.total_return > 0 else '❌'} |
| Sharpe Ratio | {report.sharpe_ratio:.2f} | {'✅' if report.sharpe_ratio >= 1.0 else '❌'} |
| 最大回撤 | {report.max_drawdown:.2f}% | {'✅' if report.max_drawdown <= 30 else '❌'} |
| 勝率 | {report.win_rate:.2f}% | {'✅' if report.win_rate >= 40 else '❌'} |
| 交易次數 | {report.total_trades} | {'✅' if report.total_trades >= 30 else '⚠️'} |

---

## 評估結果

**分數**: {report.evaluation_score:.0f}/100

{report.evaluation_summary}

### 優勢
"""
        
        for s in report.strengths:
            md += f"- {s}\n"
        
        md += "\n### 劣勢\n"
        for w in report.weaknesses:
            md += f"- {w}\n"
        
        md += "\n### 建議\n"
        for r in report.recommendations:
            md += f"- {r}\n"
        
        md += f"""

---

## 最終決定

"""
        
        if report.approved:
            md += f"""✅ **已批准**

{report.approval_notes}
"""
        else:
            md += f"""⏳ **待批准**

請審閱以上報告並決定是否批准此策略。
"""
        
        return md
    
    def format_report_compact(self, report: StrategyReport) -> str:
        """
        格式化簡短報告
        
        Args:
            report: 策略報告
            
        Returns:
            str: 簡短報告
        """
        status = "✅" if report.evaluation_passed else "❌"
        
        return f"""
╔══════════════════════════════════════════════════════════╗
║             策略研發摘要 - {report.strategy_name:<20}║
╠══════════════════════════════════════════════════════════╣
║ 收益率: {report.total_return:>7.2f}%  |  Sharpe: {report.sharpe_ratio:>5.2f}          ║
║ 回撤:   {report.max_drawdown:>7.2f}%  |  勝率:   {report.win_rate:>5.1f}%          ║
║ 評分:   {report.evaluation_score:>5.0f}/100  |  狀態:   {status}                      ║
╚══════════════════════════════════════════════════════════╝
"""
    
    def generate_llm_summary(
        self,
        report: StrategyReport,
    ) -> str:
        """
        使用 LLM 生成摘要
        
        Args:
            report: 策略報告
            
        Returns:
            str: LLM 生成的摘要
        """
        llm = self._get_llm()
        
        prompt = f"""
請生成以下策略的執行摘要：

## 策略資訊
- 名稱: {report.strategy_name}
- 描述: {report.strategy_description}

## 表現指標
- 總收益率: {report.total_return:.2f}%
- Sharpe Ratio: {report.sharpe_ratio:.2f}
- 最大回撤: {report.max_drawdown:.2f}%
- 勝率: {report.win_rate:.2f}%
- 評估分數: {report.evaluation_score:.0f}/100

## 優勢
{chr(10).join(['- ' + s for s in report.strengths]) if report.strengths else '無'}

## 劣勢
{chr(10).join(['- ' + w for w in report.weaknesses]) if report.weaknesses else '無'}

## 建議
{chr(10).join(['- ' + r for r in report.recommendations]) if report.recommendations else '無'}

請生成 2-3 句執行摘要，重點說明策略是否值得採用。
"""
        
        try:
            response = llm.invoke(prompt)
            return response.content
        except Exception as e:
            logger.error(f"LLM 摘要生成失敗: {e}")
            return report.evaluation_summary
    
    def save_report(
        self,
        report: StrategyReport,
        output_dir: str = "reports",
        format: str = "markdown",
    ) -> str:
        """
        保存報告
        
        Args:
            report: 策略報告
            output_dir: 輸出目錄
            format: 格式 (markdown/json)
            
        Returns:
            str: 保存的路徑
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # 檔名
        timestamp = report.created_at.strftime("%Y%m%d_%H%M%S")
        safe_name = report.strategy_name.replace(" ", "_")
        filename = f"{safe_name}_{timestamp}"
        
        if format == "markdown":
            content = self.format_report_markdown(report)
            filepath = os.path.join(output_dir, f"{filename}.md")
        else:
            content = json.dumps(
                {
                    "strategy_name": report.strategy_name,
                    "strategy_description": report.strategy_description,
                    "created_at": report.created_at.isoformat(),
                    "indicators": report.indicators,
                    "entry_rules": report.entry_rules,
                    "exit_rules": report.exit_rules,
                    "parameters": report.parameters,
                    "total_return": report.total_return,
                    "sharpe_ratio": report.sharpe_ratio,
                    "max_drawdown": report.max_drawdown,
                    "win_rate": report.win_rate,
                    "total_trades": report.total_trades,
                    "evaluation_passed": report.evaluation_passed,
                    "evaluation_score": report.evaluation_score,
                    "strengths": report.strengths,
                    "weaknesses": report.weaknesses,
                    "recommendations": report.recommendations,
                    "approved": report.approved,
                    "approval_notes": report.approval_notes,
                },
                indent=2,
            )
            filepath = os.path.join(output_dir, f"{filename}.json")
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        
        return filepath


# 便捷函數
def create_reporter(model: str = "minimax/minimax-m2.5") -> ReporterAgent:
    """建立彙報 Agent"""
    return ReporterAgent(model=model)


__all__ = [
    "ReporterAgent",
    "ReportSection",
    "StrategyReport",
    "create_reporter",
]
