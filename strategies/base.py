"""
策略基底類別

定義策略的標準介面，所有策略都應該繼承這個基底類別。
"""

from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd


class SignalType:
    """交易訊號類型"""
    HOLD = 0      # 持有/無訊號
    BUY = 1       # 買入訊號
    SELL = -1     # 賣出訊號


class BaseStrategy(ABC):
    """
    策略基底類別

    所有策略都應該繼承這個類別並實作必要的方法。
    """

    def __init__(self, name: Optional[str] = None):
        """
        初始化策略

        Args:
            name: 策略名稱
        """
        self.name = name or self.__class__.__name__
        self.data: Optional[pd.DataFrame] = None

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        產生交易訊號

        這是策略的核心方法，需要由子類別實作。

        Args:
            data: 帶有 OHLCV 資料的 DataFrame

        Returns:
            包含訊號的 DataFrame，必須包含 'signal' 欄位
            - 1 = 買入
            - 0 = 持有
            - -1 = 賣出
        """
        pass

    def prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        準備資料（前處理）

        子類別可以覆寫這個方法來進行資料前處理。

        Args:
            data: 原始資料

        Returns:
            處理後的資料
        """
        # 複製避免修改原始資料
        return data.copy()

    def on_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        完整的策略執行流程

        這個方法呼叫 prepare_data 和 generate_signals。

        Args:
            data: 原始 OHLCV 資料

        Returns:
            包含訊號的 DataFrame
        """
        # 儲存資料引用
        self.data = data.copy()

        # 前處理
        prepared = self.prepare_data(self.data)

        # 產生訊號
        result = self.generate_signals(prepared)

        return result

    def get_params(self) -> dict:
        """
        取得策略參數

        子類別應該覆寫這個方法來回傳可調參數。

        Returns:
            參數字典
        """
        return {}

    def __repr__(self) -> str:
        return f"<{self.name}>"


# ============================================================================
# 訊號相關工具函數
# ============================================================================

def create_signal_column(df: pd.DataFrame, signal_values: list) -> pd.DataFrame:
    """
    在 DataFrame 中新增訊號欄位

    Args:
        df: DataFrame
        signal_values: 訊號值列表

    Returns:
        帶有 'signal' 欄位的 DataFrame
    """
    df = df.copy()
    df["signal"] = signal_values
    return df


def signals_to_positions(signals: pd.Series) -> pd.Series:
    """
    將訊號轉換為實際持仓

    假設訊號改變時立即執行交易。

    Args:
        signals: 訊號序列

    Returns:
        持仓序列
    """
    positions = signals.copy()
    # 持仓 = 累計訊號（假設訊號改變時才調整仓位）
    # 這裡假設訊號是目標仓位（-1, 0, 1）
    positions = positions.fillna(0)
    return positions
