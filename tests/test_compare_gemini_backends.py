from types import SimpleNamespace

from agents.strategy_developer_agent import StrategyDeveloperAgent
from scripts.compare_gemini_backends import _analyze_raw_response, build_report


def test_analyze_raw_response_accepts_complete_structured_code():
    agent = StrategyDeveloperAgent()
    raw = """<SUMMARY>
ok
</SUMMARY>
<ASSUMPTIONS>
- none
</ASSUMPTIONS>
<CODE>
from strategies.base import BaseStrategy, SignalType
import pandas as pd

class DemoStrategy(BaseStrategy):
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        if "datetime" not in df.columns:
            df["datetime"] = df.index
        df["signal"] = SignalType.HOLD
        return df
</CODE>"""

    result = _analyze_raw_response(agent, raw)

    assert result["success"] is True
    assert result["syntax_ok"] is True
    assert result["contains_generate_signals"] is True


def test_build_report_preserves_style_and_backend_results():
    report = build_report(
        spec_name="simple_ma",
        model="gemini-2.5-pro",
        style="default",
        results=[{"backend": "google_genai_sdk", "success": False}],
    )

    assert report["spec_name"] == "simple_ma"
    assert report["style"] == "default"
    assert report["results"][0]["backend"] == "google_genai_sdk"
