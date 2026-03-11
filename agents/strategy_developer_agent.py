#!/usr/bin/env python3
"""
Strategy Developer Agent - 策略研發 Agent

職責：
- 根據市場狀況分析，開發新的交易策略
- 結合現有策略經驗，優化參數
- 生成策略規格說明書
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

from agents import AgentRole, AgentConfig, get_llm, AGENT_PROMPTS

logger = logging.getLogger(__name__)


@dataclass
class StrategySpec:
    """策略規格"""
    name: str
    description: str
    indicators: List[str] = field(default_factory=list)
    entry_rules: str = ""
    exit_rules: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    timeframe: str = "1h"
    risk_level: str = "medium"


class StrategyDeveloperAgent:
    """
    策略研發 Agent
    
    使用 LLM 根據市場環境和現有策略經驗，開發新的交易策略
    """
    
    def __init__(
        self,
        model: str = "minimax/minimax-chat",
        temperature: float = 0.8,
    ):
        self.model = model
        self.temperature = temperature
        self.llm = None
        
        # 系統 Prompt
        self.system_prompt = AGENT_PROMPTS.get(
            AgentRole.STRATEGY_DEVELOPER,
            """你是一個量化策略開發專家。
            
你的職責：
- 根據市場狀況設計交易策略
- 優化策略參數
- 識別新的交易機會

請提供：
1. 策略建議
2. 參數優化建議
3. 風險調整後的預期收益"""
        )
    
    def _get_llm(self):
        """懒加载 LLM"""
        if self.llm is None:
            config = AgentConfig(
                role=AgentRole.STRATEGY_DEVELOPER,
                model=self.model,
                temperature=self.temperature,
                system_prompt=self.system_prompt,
            )
            self.llm = get_llm(config)
        return self.llm
    
    def develop_strategy(
        self,
        market_analysis: str,
        existing_strategies: List[str] = None,
        target_metrics: Dict[str, float] = None,
    ) -> StrategySpec:
        """
        開發新策略
        
        Args:
            market_analysis: 市場分析結果
            existing_strategies: 現有策略列表
            target_metrics: 目標指標 (如 Sharpe > 1.5)
            
        Returns:
            StrategySpec: 策略規格
        """
        llm = self._get_llm()
        
        # 構建 prompt
        strategies_text = ", ".join(existing_strategies) if existing_strategies else "無"
        metrics_text = ""
        if target_metrics:
            metrics_text = "\n目標指標：" + ", ".join([
                f"{k} > {v}" for k, v in target_metrics.items()
            ])
        
        prompt = f"""
請根據以下資訊，開發一個新的交易策略：

## 市場分析
{market_analysis}

## 現有策略
{strategies_text}
{metrics_text}

## 輸出格式 (JSON)
請嚴格以下格式輸出，不要有額外文字：
{{
    "name": "策略名稱",
    "description": "策略簡短描述",
    "indicators": ["MA", "RSI", "MACD"],
    "entry_rules": "進場規則描述",
    "exit_rules": "出場規則描述",
    "parameters": {{
        "param1": value1,
        "param2": value2
    }},
    "timeframe": "1h",
    "risk_level": "low/medium/high"
}}

請確保輸出的策略是創新的，且與現有策略有所不同。
"""
        
        try:
            response = llm.invoke(prompt)
            content = response.content
            
            # 解析 JSON
            # 嘗試找到 JSON 區塊
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            data = json.loads(content.strip())
            
            return StrategySpec(
                name=data.get("name", "New Strategy"),
                description=data.get("description", ""),
                indicators=data.get("indicators", []),
                entry_rules=data.get("entry_rules", ""),
                exit_rules=data.get("exit_rules", ""),
                parameters=data.get("parameters", {}),
                timeframe=data.get("timeframe", "1h"),
                risk_level=data.get("risk_level", "medium"),
            )
            
        except Exception as e:
            logger.error(f"策略開發失敗: {e}")
            # 返回默認策略
            return StrategySpec(
                name="Fallback Strategy",
                description="基於簡單均線的策略",
                indicators=["MA(20)", "MA(50)"],
                entry_rules="短均線上穿長均線買入",
                exit_rules="短均線下穿長均線賣出",
                parameters={"fast_ma": 20, "slow_ma": 50},
                timeframe="1h",
                risk_level="medium",
            )
    
    def optimize_strategy(
        self,
        strategy: StrategySpec,
        backtest_results: Dict[str, Any],
    ) -> StrategySpec:
        """
        根據回測結果優化策略
        
        Args:
            strategy: 現有策略
            backtest_results: 回測結果
            
        Returns:
            StrategySpec: 優化後的策略
        """
        llm = self._get_llm()
        
        prompt = f"""
請根據以下回測結果，優化策略參數：

## 原始策略
- 名稱: {strategy.name}
- 描述: {strategy.description}
- 指標: {', '.join(strategy.indicators)}
- 參數: {json.dumps(strategy.parameters)}
- 進場規則: {strategy.entry_rules}
- 出場規則: {strategy.exit_rules}

## 回測結果
- 總收益率: {backtest_results.get('total_return', 0):.2f}%
- Sharpe Ratio: {backtest_results.get('sharpe_ratio', 0):.2f}
- 最大回撤: {backtest_results.get('max_drawdown', 0):.2f}%
- 勝率: {backtest_results.get('win_rate', 0):.2f}%
- 交易次數: {backtest_results.get('total_trades', 0)}

## 問題診斷
{self._diagnose_results(backtest_results)}

## 輸出格式 (JSON)
請嚴格以下格式輸出：
{{
    "name": "優化後策略名稱",
    "description": "優化說明",
    "indicators": ["保持或修改指標"],
    "entry_rules": "修改後的進場規則",
    "exit_rules": "修改後的出不規則",
    "parameters": {{
        "param1": new_value1,
        "param2": new_value2
    }},
    "timeframe": "保持或修改",
    "risk_level": "low/medium/high"
}}
"""
        
        try:
            response = llm.invoke(prompt)
            content = response.content
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            data = json.loads(content.strip())
            
            return StrategySpec(
                name=data.get("name", strategy.name + "_optimized"),
                description=data.get("description", strategy.description),
                indicators=data.get("indicators", strategy.indicators),
                entry_rules=data.get("entry_rules", strategy.entry_rules),
                exit_rules=data.get("exit_rules", strategy.exit_rules),
                parameters=data.get("parameters", strategy.parameters),
                timeframe=data.get("timeframe", strategy.timeframe),
                risk_level=data.get("risk_level", strategy.risk_level),
            )
            
        except Exception as e:
            logger.error(f"策略優化失敗: {e}")
            return strategy
    
    def _diagnose_results(self, results: Dict[str, Any]) -> str:
        """診斷回測結果"""
        issues = []
        
        sharpe = results.get("sharpe_ratio", 0)
        if sharpe < 1.0:
            issues.append("- Sharpe Ratio 低於 1.0，風險調整收益不佳")
        elif sharpe > 2.0:
            issues.append(f"- Sharpe Ratio 很高 ({sharpe:.2f})，可能過擬合")
        
        drawdown = results.get("max_drawdown", 0)
        if drawdown > 30:
            issues.append(f"- 最大回撤過大 ({drawdown:.1f}%)")
        
        win_rate = results.get("win_rate", 0)
        if win_rate < 40:
            issues.append(f"- 勝率偏低 ({win_rate:.1f}%)")
        
        trades = results.get("total_trades", 0)
        if trades < 10:
            issues.append(f"- 交易次數過少 ({trades})，樣本不足")
        
        if not issues:
            return "無明顯問題"
        
        return "\n".join(issues)
    
    def generate_strategy_code(self, spec: StrategySpec) -> str:
        """
        生成策略代碼
        
        Args:
            spec: 策略規格
            
        Returns:
            str: Python 代碼
        """
        llm = self._get_llm()
        
        prompt = f"""
請生成完整的 Python 策略代碼：

## 策略規格
- 名稱: {spec.name}
- 描述: {spec.description}
- 指標: {', '.join(spec.indicators)}
- 進場規則: {spec.entry_rules}
- 出場規則: {spec.exit_rules}
- 參數: {json.dumps(spec.parameters)}
- 時間框架: {spec.timeframe}

## 輸出要求
1. 繼承 strategies/base.py 中的 BaseStrategy
2. 實現 required_indicators, calculate_signals 方法
3. 包含完整的 DocString
4. 代碼要可以直接使用

## 現有策略範例 (ma_crossover.py)
```python
\"\"\"MA Crossover Strategy\"\"\"

from strategies.base import BaseStrategy


class MACrossoverStrategy(BaseStrategy):
    \"\"\"
    移動平均線交叉策略
    
    進場：短均線上穿長均線
    出場：短均線下穿長均線
    \"\"\"
    
    def __init__(self, fast_ma: int = 20, slow_ma: int = 50):
        super().__init__(name="MA_Crossover")
        self.fast_ma = fast_ma
        self.slow_ma = slow_ma
    
    @property
    def required_indicators(self) -> list:
        return [f"MA_{self.fast_ma}", f"MA_{self.slow_ma}"]
    
    def calculate_signals(self, data, indicators) -> dict:
        \"\"\"計算交易信號\"\"\"
        fast = indicators[f"MA_{self.fast_ma}"]
        slow = indicators[f"MA_{self.slow_ma}"]
        
        # 最後一根K線的信號
        signal = 0
        if fast.iloc[-1] > slow.iloc[-1] and fast.iloc[-2] <= slow.iloc[-2]:
            signal = 1  # 買入
        elif fast.iloc[-1] < slow.iloc[-1] and fast.iloc[-2] >= slow.iloc[-2]:
            signal = -1  # 賣出
        
        return {{"signal": signal, "strength": abs(fast.iloc[-1] - slow.iloc[-1]) / slow.iloc[-1]}}
```

請生成 {spec.name} 的代碼：
"""
        
        try:
            response = llm.invoke(prompt)
            return response.content
        except Exception as e:
            logger.error(f"代碼生成失敗: {e}")
            return ""


# 便捷函數
def create_strategy_developer(
    model: str = "minimax/minimax-chat",
) -> StrategyDeveloperAgent:
    """建立策略研發 Agent"""
    return StrategyDeveloperAgent(model=model)


__all__ = [
    "StrategyDeveloperAgent",
    "StrategySpec",
    "create_strategy_developer",
]
