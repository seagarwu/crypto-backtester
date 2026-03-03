"""
移動平均線交叉策略 (Moving Average Crossover Strategy)

一個最基本的趨勢追蹤策略：
- 黃金交叉（短均線從下方穿越長均線）→ 買入訊號
- 死亡交叉（短均線從上方穿越長均線）→ 賣出訊號

只支援 long 方向。
"""

from typing import Optional

import pandas as pd

from .base import BaseStrategy, SignalType


class MACrossoverStrategy(BaseStrategy):
    """
    移動平均線交叉策略

    參數:
        short_window: 短期均線週期（預設 20）
        long_window: 長期均線週期（預設 50）
    """

    def __init__(
        self,
        short_window: int = 20,
        long_window: int = 50,
        name: Optional[str] = None,
    ):
        """
        初始化均線交叉策略

        Args:
            short_window: 短期均線週期
            long_window: 長期均線週期
        """
        super().__init__(name="MA_Crossover")
        self.short_window = short_window
        self.long_window = long_window

        # 驗證參數
        if short_window >= long_window:
            raise ValueError("short_window 必須小於 long_window")
        if short_window < 1 or long_window < 1:
            raise ValueError("視窗大小必須 >= 1")

    def get_params(self) -> dict:
        """取得策略參數"""
        return {
            "short_window": self.short_window,
            "long_window": self.long_window,
        }

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        產生交易訊號

        Args:
            data: 帶有 OHLCV 資料的 DataFrame，必須包含 'close' 欄位

        Returns:
            包含訊號的 DataFrame
        """
        df = data.copy()

        # 計算移動平均線
        df["ma_short"] = df["close"].rolling(window=self.short_window).mean()
        df["ma_long"] = df["close"].rolling(window=self.long_window).mean()

        # 初始化訊號
        df["signal"] = SignalType.HOLD

        # 產生交叉訊號
        # 黃金交叉：短均線從下往上穿越長均線
        # 死亡交叉：短均線從上往下穿越長均線
        for i in range(1, len(df)):
            # 必須等到有足夠的均線資料
            if pd.isna(df.loc[i, "ma_short"]) or pd.isna(df.loc[i, "ma_long"]):
                continue
            if pd.isna(df.loc[i - 1, "ma_short"]) or pd.isna(df.loc[i - 1, "ma_long"]):
                continue

            # 黃金交叉：昨天 short <= long，今天 short > long
            if (
                df.loc[i - 1, "ma_short"] <= df.loc[i - 1, "ma_long"]
            ) and (
                df.loc[i, "ma_short"] > df.loc[i, "ma_long"]
            ):
                df.loc[i, "signal"] = SignalType.BUY

            # 死亡交叉：昨天 short >= long，今天 short < long
            elif (
                df.loc[i - 1, "ma_short"] >= df.loc[i - 1, "ma_long"]
            ) and (
                df.loc[i, "ma_short"] < df.loc[i, "ma_long"]
            ):
                df.loc[i, "signal"] = SignalType.SELL

        # 只保留我們需要的欄位
        result_columns = ["datetime", "open", "high", "low", "close", "volume"]
        if "ma_short" in df.columns:
            result_columns.append("ma_short")
        if "ma_long" in df.columns:
            result_columns.append("ma_long")
        result_columns.append("signal")

        return df[result_columns]

    def __repr__(self) -> str:
        return f"<MACrossoverStrategy: short={self.short_window}, long={self.long_window}>"


# ============================================================================
# 便捷函數
# ============================================================================

def create_ma_crossover_strategy(
    short_window: int = 20,
    long_window: int = 50,
) -> MACrossoverStrategy:
    """
    建立均線交叉策略的便捷函數

    Args:
        short_window: 短期均線週期
        long_window: 長期均線週期

    Returns:
        MACrossoverStrategy 實例
    """
    return MACrossoverStrategy(short_window=short_window, long_window=long_window)
