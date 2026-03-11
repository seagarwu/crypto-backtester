"""Generated Strategy: BBandMomentumStrategy

自動生成的策略代碼
"""

from strategies.base import BaseStrategy, SignalType
import pandas as pd

class BBandMomentumStrategy(BaseStrategy):
    """BBand 動量策略 - 模擬生成的代碼"""
    
    def __init__(self, bband_period: int = 20, bband_std: float = 2.0):
        super().__init__(name="BBandMomentum")
        self.bband_period = bband_period
        self.bband_std = bband_std
        self.required_indicators = [
            f"BBAND_{bband_period}",
            f"MA_{bband_period}"
        ]
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """生成交易信號"""
        signals = pd.DataFrame({
            'datetime': data['datetime'].values,
            'signal': SignalType.HOLD
        })
        
        # 簡單邏輯：收盤價觸及下軌買入，觸及上軌賣出
        for i in range(self.bband_period, len(data)):
            # 這裡應該有真實的 BBand 計算邏輯
            # 模擬：隨機產生信號
            if i % 20 == 0:
                signals.loc[i, 'signal'] = SignalType.BUY
            elif i % 25 == 0:
                signals.loc[i, 'signal'] = SignalType.SELL
        
        return signals
