"""Generated Strategy: TestStrategy

自動生成的策略代碼
"""

from strategies.base import BaseStrategy, SignalType
import pandas as pd

class TestStrategy(BaseStrategy):
    def __init__(self, param: int = 20):
        super().__init__(name="Test")
        self.param = param
        self.required_indicators = ["MA_20"]

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame({
 '            '"datetime"': data['"datetime"'],' 
            'signal': SignalType.HOLD
        })
        return signals
