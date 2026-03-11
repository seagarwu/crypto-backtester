"""Generated Strategy: LoadTestStrategy

自動生成的策略代碼
"""

from strategies.base import BaseStrategy, SignalType
import pandas as pd

class LoadTestStrategy(BaseStrategy):
    def __init__(self, period: int = 20):
        super().__init__(name="LoadTest")
        self.period = period
        self.required_indicators = [f"MA_{period}"]

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame({
 '            '"datetime"': data['"datetime"'],' 
            'signal': SignalType.HOLD
        })
        return signals
