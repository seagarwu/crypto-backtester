from types import SimpleNamespace

from agents.strategy_developer_agent import StrategyDeveloperAgent
from scripts.run_engineer_prompt_probe import (
    analyze_probe_output,
    build_probe_specs,
    build_probe_report,
    run_probe_variant,
)


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def invoke(self, payload):
        self.calls.append(payload)
        content = self.responses.pop(0)
        return SimpleNamespace(content=content)


def test_build_probe_specs_exposes_simple_ma_and_rsi_macd():
    specs = build_probe_specs()

    assert set(specs) == {"simple_ma", "simple_rsi_macd"}
    assert specs["simple_rsi_macd"].indicators == ["RSI_14", "MACD_12_26_9"]


def test_analyze_probe_output_reports_missing_code():
    analysis = analyze_probe_output("", parse_error="Missing <CODE> block")

    assert analysis["success"] is False
    assert "Missing <CODE> block" in analysis["issues"]
    assert "No code generated" in analysis["issues"]


def test_analyze_probe_output_rejects_generate_signals_without_return():
    code = """from strategies.base import BaseStrategy, SignalType
import pandas as pd

class DemoStrategy(BaseStrategy):
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df["signal"] = SignalType.HOLD
"""

    analysis = analyze_probe_output(code, parse_error=None)

    assert analysis["success"] is False
    assert "generate_signals has no return statement" in analysis["issues"]


def test_run_probe_variant_handles_structured_system_success():
    agent = StrategyDeveloperAgent()
    spec = build_probe_specs()["simple_ma"]
    llm = FakeLLM(
        [
            """<SUMMARY>
ok
</SUMMARY>
<ASSUMPTIONS>
- none
</ASSUMPTIONS>
<CODE>
from strategies.base import BaseStrategy, SignalType
import pandas as pd

class DemoStrategy(BaseStrategy):
    def __init__(self, name: str | None = None):
        super().__init__(name=name or "Demo")
        self.required_indicators = []

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        if "datetime" not in df.columns:
            df["datetime"] = df.index
        df["signal"] = SignalType.HOLD
        return df
</CODE>"""
        ]
    )

    result = run_probe_variant(agent=agent, spec=spec, variant="structured_system", llm=llm)

    assert result["success"] is True
    assert result["prompt_mode"] == "system_plus_human"
    assert result["syntax_ok"] is True
    assert "generate_signals" in result["code"]
    assert isinstance(llm.calls[0], list)


def test_run_probe_variant_handles_openhands_structured_system_success():
    agent = StrategyDeveloperAgent()
    spec = build_probe_specs()["simple_ma"]
    llm = FakeLLM(
        [
            """<SUMMARY>
ok
</SUMMARY>
<ASSUMPTIONS>
- none
</ASSUMPTIONS>
<CODE>
from strategies.base import BaseStrategy, SignalType
import pandas as pd

class DemoStrategy(BaseStrategy):
    def __init__(self, name: str | None = None):
        super().__init__(name=name or "Demo")
        self.required_indicators = []

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        if "datetime" not in df.columns:
            df["datetime"] = df.index
        df["signal"] = SignalType.HOLD
        return df
</CODE>"""
        ]
    )

    result = run_probe_variant(agent=agent, spec=spec, variant="structured_system_openhands", llm=llm)

    assert result["success"] is True
    assert result["prompt_mode"] == "system_plus_human_openhands"
    assert result["syntax_ok"] is True
    assert "generate_signals" in result["code"]
    assert isinstance(llm.calls[0], list)


def test_run_probe_variant_marks_missing_code_block_failure():
    agent = StrategyDeveloperAgent()
    spec = build_probe_specs()["simple_rsi_macd"]
    llm = FakeLLM(["這不是合法 structured response"])

    result = run_probe_variant(agent=agent, spec=spec, variant="structured_user_only", llm=llm)

    assert result["success"] is False
    assert "Missing <CODE> block in structured response" in result["issues"]
    assert result["code"] == ""


def test_build_probe_report_summarizes_successful_and_failed_variants():
    report = build_probe_report(
        spec_name="simple_ma",
        model="gemini-2.5-pro",
        results=[
            {"variant": "legacy_inline", "success": False},
            {"variant": "structured_system_openhands", "success": True},
        ],
    )

    assert report["summary"]["successful_variants"] == ["structured_system_openhands"]
    assert report["summary"]["failed_variants"] == ["legacy_inline"]
