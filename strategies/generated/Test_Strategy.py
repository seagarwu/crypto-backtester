"""Generated Strategy: Test_Strategy

自動生成的策略代碼
"""

from strategies.base import BaseStrategy

class TestStrategy(BaseStrategy):
    def __init__(self, param1: int = 10):
        super().__init__(name="TestStrategy")
        self.param1 = param1
    
    @property
    def required_indicators(self):
        return []
    
    def calculate_signals(self, data, indicators):
        return {"signal": 0}
