#!/usr/bin/env python3
"""
Strategy Developer Agent 測試
"""

import pytest
import sys
import os
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.strategy_developer_agent import StrategyDeveloperAgent, StrategySpec


class TestStrategySpec:
    """測試策略規格"""
    
    def test_create_strategy_spec(self):
        spec = StrategySpec(
            name="Test Strategy",
            description="Test description",
            indicators=["MA_20", "RSI_14"],
            entry_rules="MA_20 > MA_50",
            exit_rules="MA_20 < MA_50",
            parameters={"fast_ma": 20, "slow_ma": 50},
            timeframe="1h",
            risk_level="medium",
        )
        
        assert spec.name == "Test Strategy"
        assert len(spec.indicators) == 2
        assert spec.parameters["fast_ma"] == 20
    
    def test_default_values(self):
        spec = StrategySpec(name="Default", description="Default description")
        
        assert spec.name == "Default"
        assert spec.description == "Default description"
        assert spec.indicators == []
        assert spec.risk_level == "medium"
        assert spec.timeframe == "1h"


class TestStrategyDeveloperAgent:
    """測試策略研發 Agent"""
    
    def test_agent_init(self):
        agent = StrategyDeveloperAgent()
        
        assert agent.model == "gemini-2.5-pro"
        assert agent.temperature == 0.8
        assert agent.llm is None  # 懒加载
    
    def test_agent_with_custom_model(self):
        agent = StrategyDeveloperAgent(model="gpt-4", temperature=0.5)
        
        assert agent.model == "gpt-4"
        assert agent.temperature == 0.5
    
    def test_diagnose_results_good(self):
        agent = StrategyDeveloperAgent()
        
        results = {
            "sharpe_ratio": 3.0,  # Very high
            "max_drawdown": 10.0,
            "win_rate": 60.0,
            "total_trades": 100,
        }
        
        diagnosis = agent._diagnose_results(results)
        
        # Very high Sharpe should trigger "too high" warning
        assert "Sharpe Ratio" in diagnosis
    
    def test_diagnose_results_bad(self):
        agent = StrategyDeveloperAgent()
        
        results = {
            "sharpe_ratio": 0.5,
            "max_drawdown": 50.0,
            "win_rate": 30.0,
            "total_trades": 5,
        }
        
        diagnosis = agent._diagnose_results(results)
        
        assert "Sharpe Ratio 低於 1.0" in diagnosis
        assert "最大回撤過大" in diagnosis
        assert "交易次數過少" in diagnosis

    def test_normalize_backtest_results_accepts_report_object(self):
        agent = StrategyDeveloperAgent()
        report = SimpleNamespace(
            total_return=12.5,
            sharpe_ratio=1.2,
            max_drawdown=18.0,
            win_rate=46.0,
            total_trades=40,
            profit_factor=1.3,
        )

        normalized = agent._normalize_backtest_results(report)

        assert normalized["total_return"] == 12.5
        assert normalized["max_drawdown"] == 18.0

    def test_extract_strategy_context_prefers_strategy_spec_section(self):
        agent = StrategyDeveloperAgent()

        md_context = """# Test

## 討論歷史
- 2026-03-12 18:21: 用戶: "好"
- 18:21:32 | INFO | httpx | HTTP Request: POST ...

## 策略規格
- 名稱: BTCUSDT_BBand_Reversion
- 描述: 測試策略
- 指標: ['BBAND']

## 生成檔案
- /tmp/generated.py
"""

        context = agent._extract_strategy_context(md_context)

        assert "名稱: BTCUSDT_BBand_Reversion" in context
        assert "HTTP Request" not in context
        assert "/tmp/generated.py" not in context

    def test_parse_json_response_and_clean_code_block(self):
        agent = StrategyDeveloperAgent()
        raw = """```json
{
  "summary": "test",
  "assumptions": ["a1"],
  "code": "```python\\nfrom x import y\\n```"
}
```"""

        data = agent._parse_json_response(raw)
        code = agent._clean_code_block(data["code"])

        assert data["summary"] == "test"
        assert data["assumptions"] == ["a1"]
        assert code == "from x import y"

    def test_structured_prompt_includes_engineer_agent_context(self):
        agent = StrategyDeveloperAgent()
        spec = StrategySpec(name="Demo", description="demo")

        prompt = agent._build_structured_code_prompt(
            spec=spec,
            context="local context",
            feedback_text="{}",
            previous_code="",
        )

        assert "工程規則與工具上下文" in prompt
        assert "Engineer Agent Rules" in prompt
        assert "Shared Tool Capabilities" in prompt

    def test_parse_structured_response(self):
        agent = StrategyDeveloperAgent()
        raw = """<SUMMARY>
refine entry logic
</SUMMARY>
<ASSUMPTIONS>
- use close price
- long only
</ASSUMPTIONS>
<CODE>
from x import y
</CODE>"""

        data = agent._parse_structured_response(raw)

        assert data["summary"] == "refine entry logic"
        assert data["assumptions"] == ["use close price", "long only"]
        assert data["code"] == "from x import y"

    def test_parse_structured_response_falls_back_to_python_extraction(self):
        agent = StrategyDeveloperAgent()
        raw = """這是策略實作說明

```python
from strategies.base import BaseStrategy

class DemoStrategy(BaseStrategy):
    pass
```

補充說明結束
"""

        data = agent._parse_structured_response(raw)

        assert "class DemoStrategy" in data["code"]
        assert data["summary"] == ""

    def test_clean_code_block_strips_markdown_noise(self):
        agent = StrategyDeveloperAgent()
        raw = """說明文字

```python
from strategies.base import BaseStrategy

class DemoStrategy(BaseStrategy):
    pass
```

- 額外說明
"""

        code = agent._clean_code_block(raw)

        assert code.startswith("from strategies.base import BaseStrategy")
        assert code.endswith("pass")

    def test_generate_strategy_code_structured_preserves_raw_on_fallback(self):
        agent = StrategyDeveloperAgent()
        spec = StrategySpec(name="Demo", description="demo")

        class FakeLLM:
            def __init__(self):
                self.calls = 0

            def invoke(self, prompt):
                self.calls += 1
                if self.calls == 1:
                    return SimpleNamespace(content="這不是合法 structured response")
                return SimpleNamespace(
                    content="""from strategies.base import BaseStrategy, SignalType
import pandas as pd

class DemoStrategy(BaseStrategy):
    @property
    def required_indicators(self):
        return []

    def calculate_signals(self, data: pd.DataFrame, indicators: dict) -> dict:
        return {"signal": SignalType.HOLD, "strength": 0.0}

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        if "datetime" not in df.columns:
            df["datetime"] = df.index
        df["signal"] = SignalType.HOLD
        return df
"""
                )

        agent.llm = FakeLLM()

        result = agent.generate_strategy_code_structured(spec)

        assert "class DemoStrategy" in result.code
        assert "[structured_attempt]" in result.raw_response
        assert "[legacy_fallback]" in result.raw_response
        assert "這不是合法 structured response" in result.raw_response

    def test_revise_strategy_code_does_not_reuse_previous_broken_code(self):
        agent = StrategyDeveloperAgent()
        spec = StrategySpec(name="Demo", description="demo")
        previous_code = "class BrokenStrategy("

        class FakeLLM:
            def __init__(self):
                self.calls = 0

            def invoke(self, prompt):
                self.calls += 1
                if self.calls == 1:
                    return SimpleNamespace(content="仍然不是合法 structured response")
                return SimpleNamespace(
                    content="""from strategies.base import BaseStrategy, SignalType
import pandas as pd

class DemoStrategy(BaseStrategy):
    @property
    def required_indicators(self):
        return []

    def calculate_signals(self, data: pd.DataFrame, indicators: dict) -> dict:
        return {"signal": SignalType.HOLD, "strength": 0.0}

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        if "datetime" not in df.columns:
            df["datetime"] = df.index
        df["signal"] = SignalType.HOLD
        return df
"""
                )

        agent.llm = FakeLLM()

        result = agent.revise_strategy_code(
            spec=spec,
            feedback={"validation_issues": ["Syntax error"]},
            previous_code=previous_code,
        )

        assert result.code != previous_code
        assert "class DemoStrategy" in result.code
        assert "legacy regeneration" in result.summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
