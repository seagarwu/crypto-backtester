"""
布林帶策略 (Bollinger Bands Strategy)

根據用戶的盤整盤策略邏輯：
- 進場：價格觸及長週期 BBand 下軌（支撐線）或 MA 時買入
- 出場：價格觸及長週期 BBand 上軌（壓力線）時賣出
- 長週期指標雜訊較少，適合作為進出場依據

支持多時間框架分析和 Optuna 優化。
"""

from typing import Optional, List, Dict, Any

import pandas as pd
import numpy as np

from .base import BaseStrategy, SignalType


class BBandStrategy(BaseStrategy):
    """
    布林帶策略
    
    參數:
        bband_period: 布林帶週期 (默認 20)
        bband_std: 標準差倍數 (默認 2.0)
        ma_period: MA 週期，用於輔助判斷 (默認 50)
        entry_threshold: 進場閾值，低於此倍數視為觸及支撐 (默認 1.0 = 下軌)
        exit_threshold: 出場閾值，高於此倍數視為觸及壓力 (默認 1.0 = 上軌)
        use_ma_confirm: 是否使用 MA 確認信號 (默認 False)
    """

    def __init__(
        self,
        bband_period: int = 20,
        bband_std: float = 2.0,
        ma_period: int = 50,
        entry_threshold: float = 1.0,
        exit_threshold: float = 1.0,
        use_ma_confirm: bool = False,
        name: Optional[str] = None,
    ):
        """
        初始化布林帶策略

        Args:
            bband_period: 布林帶計算週期
            bband_std: 標準差倍數
            ma_period: MA 週期
            entry_threshold: 進場閾值 (0.5 = 下軌和中軌中間, 1.0 = 下軌)
            exit_threshold: 出場閾值 (1.0 = 上軌, 1.5 = 上軌和中軌中間)
            use_ma_confirm: 是否使用 MA 確認
        """
        super().__init__(name="BBand_Strategy")
        
        self.bband_period = bband_period
        self.bband_std = bband_std
        self.ma_period = ma_period
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.use_ma_confirm = use_ma_confirm
        
        # 設定所需指標
        self.required_indicators = [
            f"BBand_{bband_period}_{bband_std}",
            f"MA_{ma_period}"
        ]
        
        # 驗證參數
        if bband_period < 1:
            raise ValueError("bband_period must be >= 1")
        if bband_std < 0.1:
            raise ValueError("bband_std must be > 0")
        if ma_period < 1:
            raise ValueError("ma_period must be >= 1")

    def get_params(self) -> dict:
        """取得策略參數"""
        return {
            "bband_period": self.bband_period,
            "bband_std": self.bband_std,
            "ma_period": self.ma_period,
            "entry_threshold": self.entry_threshold,
            "exit_threshold": self.exit_threshold,
            "use_ma_confirm": self.use_ma_confirm,
        }

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """計算所需的技術指標"""
        df = data.copy()
        
        # 計算布林帶
        df["bb_middle"] = df["close"].rolling(window=self.bband_period).mean()
        rolling_std = df["close"].rolling(window=self.bband_period).std()
        df["bb_upper"] = df["bb_middle"] + (rolling_std * self.bband_std)
        df["bb_lower"] = df["bb_middle"] - (rolling_std * self.bband_std)
        
        # 計算價格相對布林帶的位置
        # ratio = 0 表示觸及下軌, = 1 表示觸及上軌
        bb_range = df["bb_upper"] - df["bb_lower"]
        df["bb_position"] = np.where(
            bb_range > 0,
            (df["close"] - df["bb_lower"]) / bb_range,
            0.5
        )
        
        # 計算 MA
        df["ma"] = df["close"].rolling(window=self.ma_period).mean()
        
        # 計算價格與 MA 的相對位置
        df["price_vs_ma"] = df["close"] - df["ma"]
        
        return df

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        產生交易訊號

        進場邏輯：
        - 價格觸及 BBand 下軌 (bb_position <= entry_threshold) 且
        - 可選：價格在 MA 上方 (price_vs_ma > 0)
        
        出場邏輯：
        - 價格觸及 BBand 上軌 (bb_position >= exit_threshold) 或
        - 可選：價格在 MA 下方 (price_vs_ma < 0)

        Args:
            data: 帶有 OHLCV 資料的 DataFrame，必須包含 'close' 欄位

        Returns:
            包含訊號的 DataFrame
        """
        df = self.calculate_indicators(data)
        
        # 初始化訊號
        df["signal"] = SignalType.HOLD
        
        # 進場條件：價格觸及下軌
        entry_condition = df["bb_position"] <= self.entry_threshold
        
        if self.use_ma_confirm:
            # 需要價格在 MA 上方才進場 (做多)
            entry_condition = entry_condition & (df["price_vs_ma"] > 0)
        
        # 出場條件：價格觸及上軌
        exit_condition = df["bb_position"] >= self.exit_threshold
        
        if self.use_ma_confirm:
            # 價格在 MA 下方時也考慮出場
            exit_condition = exit_condition | (df["price_vs_ma"] < 0)
        
        # 產生訊號
        # 從進場狀態變為觸及上軌 -> 賣出
        in_position = False
        for i in range(1, len(df)):
            if entry_condition.iloc[i] and not in_position:
                df.loc[df.index[i], "signal"] = SignalType.BUY
                in_position = True
            elif exit_condition.iloc[i] and in_position:
                df.loc[df.index[i], "signal"] = SignalType.SELL
                in_position = False
        
        # 處理最後持倉
        if in_position:
            df.loc[df.index[-1], "signal"] = SignalType.SELL
        
        return df
    
    def get_optimization_space(self) -> Dict[str, Any]:
        """取得 Optuna 優化參數空間"""
        return {
            "bband_period": {"low": 10, "high": 60, "type": "int"},
            "bband_std": {"low": 1.5, "high": 3.0, "type": "float"},
            "ma_period": {"low": 20, "high": 200, "type": "int"},
            "entry_threshold": {"low": 0.0, "high": 0.5, "type": "float"},
            "exit_threshold": {"low": 0.8, "high": 1.5, "type": "float"},
            "use_ma_confirm": {"type": "categorical", "choices": [True, False]},
        }


class MultiTimeframeBBandStrategy(BaseStrategy):
    """
    多時間框架布林帶策略
    
    結合多個時間週期的 BBand 信號：
    - 高時間週期：用於確認趨勢/盤整
    - 低時間週期：用於精確進出場
    
    用戶邏輯：長週期(4h,1d,1w)雜訊少，適合作為進出場依據
    """

    def __init__(
        self,
        # 主時間框架參數
        main_bband_period: int = 20,
        main_bband_std: float = 2.0,
        main_ma_period: int = 50,
        # 確認時間框架參數
        confirm_bband_period: int = 20,
        confirm_bband_std: float = 2.0,
        # 交易參數
        entry_threshold: float = 1.0,
        exit_threshold: float = 1.0,
        # 多時間框架確認
        require_confirm: bool = True,
        name: Optional[str] = None,
    ):
        """
        初始化多時間框架布林帶策略

        Args:
            main_bband_period: 主時間框架 BBand 週期
            main_bband_std: 主時間框架標準差倍數
            main_ma_period: 主時間框架 MA 週期
            confirm_bband_period: 確認時間框架 BBand 週期
            confirm_bband_std: 確認時間框架標準差倍數
            entry_threshold: 進場閾值
            exit_threshold: 出場閾值
            require_confirm: 是否需要確認時間框架確認信號
        """
        super().__init__(name="MultiTimeframe_BBand")
        
        self.main_bband_period = main_bband_period
        self.main_bband_std = main_bband_std
        self.main_ma_period = main_ma_period
        self.confirm_bband_period = confirm_bband_period
        self.confirm_bband_std = confirm_bband_std
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.require_confirm = require_confirm

    def calculate_bbands(self, data: pd.DataFrame, period: int, std: float) -> pd.DataFrame:
        """計算布林帶"""
        df = data.copy()
        df["bb_middle"] = df["close"].rolling(window=period).mean()
        rolling_std = df["close"].rolling(window=period).std()
        df["bb_upper"] = df["bb_middle"] + (rolling_std * std)
        df["bb_lower"] = df["bb_middle"] - (rolling_std * std)
        
        bb_range = df["bb_upper"] - df["bb_lower"]
        df["bb_position"] = np.where(
            bb_range > 0,
            (df["close"] - df["bb_lower"]) / bb_range,
            0.5
        )
        return df

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        產生交易訊號
        
        需要兩個時間框架的數據通過 main_data 和 confirm_data 傳入
        或者在 data 中包含多個時間框架的 columns
        """
        df = data.copy()
        
        # 計算主時間框架的 BBand
        df = self.calculate_bbands(df, self.main_bband_period, self.main_bband_std)
        
        # 計算確認時間框架的 BBand (如果存在)
        if "confirm_bb_position" in df.columns:
            confirm_bb = df["confirm_bb_position"]
        else:
            # 如果沒有確認框架，使用主框架
            confirm_bb = df["bb_position"]
        
        # 進場條件
        entry_condition = df["bb_position"] <= self.entry_threshold
        
        # 出場條件
        exit_condition = df["bb_position"] >= self.exit_threshold
        
        if self.require_confirm:
            # 需要確認時間框架也顯示有利信號
            entry_condition = entry_condition & (confirm_bb <= 0.6)
        
        # 初始化訊號
        df["signal"] = SignalType.HOLD
        
        # 產生訊號
        in_position = False
        for i in range(1, len(df)):
            if entry_condition.iloc[i] and not in_position:
                df.loc[df.index[i], "signal"] = SignalType.BUY
                in_position = True
            elif exit_condition.iloc[i] and in_position:
                df.loc[df.index[i], "signal"] = SignalType.SELL
                in_position = False
        
        return df
    
    def get_optimization_space(self) -> Dict[str, Any]:
        """取得 Optuna 優化參數空間"""
        return {
            "main_bband_period": {"low": 10, "high": 60, "type": "int"},
            "main_bband_std": {"low": 1.5, "high": 3.0, "type": "float"},
            "main_ma_period": {"low": 20, "high": 200, "type": "int"},
            "confirm_bband_period": {"low": 10, "high": 60, "type": "int"},
            "confirm_bband_std": {"low": 1.5, "high": 3.0, "type": "float"},
            "entry_threshold": {"low": 0.0, "high": 0.5, "type": "float"},
            "exit_threshold": {"low": 0.8, "high": 1.5, "type": "float"},
            "require_confirm": {"type": "categorical", "choices": [True, False]},
        }


# 策略注册表
STRATEGY_REGISTRY = {
    "bbands": BBandStrategy,
    "bbands_multi": MultiTimeframeBBandStrategy,
    "ma_crossover": None,  # 需要從 ma_crossover 導入
}


def get_strategy(strategy_name: str, **kwargs):
    """取得策略實例"""
    if strategy_name in STRATEGY_REGISTRY:
        strategy_class = STRATEGY_REGISTRY[strategy_name]
        if strategy_class:
            return strategy_class(**kwargs)
    
    raise ValueError(f"Unknown strategy: {strategy_name}")
