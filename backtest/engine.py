"""
回測引擎核心

提供基本的回測功能，支援：
- 初始資金設定
- 固定比例或全倉交易
- 交易成本（commission）
- 持倉追蹤
- 資產曲線計算
"""

from dataclasses import dataclass, field
from typing import Optional, List

import pandas as pd
import numpy as np


@dataclass
class Trade:
    """單筆交易記錄"""
    entry_datetime: str
    entry_price: float
    quantity: float
    direction: str  # "long" or "short"
    exit_datetime: Optional[str] = None
    exit_price: Optional[float] = None
    pnl: float = 0.0
    commission: float = 0.0


@dataclass
class Position:
    """當前持倉"""
    entry_datetime: str
    entry_price: float
    quantity: float
    direction: str = "long"


@dataclass
class BacktestResult:
    """回測結果"""
    equity_curve: pd.DataFrame
    trades: List[Trade]
    final_equity: float
    initial_capital: float
    total_return: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0


class BacktestEngine:
    """
    回測引擎

    簡化的回測實現，支援基本的前向交易模擬。
    """

    def __init__(
        self,
        initial_capital: float = 10000.0,
        commission_rate: float = 0.001,  # 0.1% 手續費
        position_size: float = 1.0,       # 1.0 = 全倉, 0.5 = 50% 倉位
        execution_price: str = "close",   # "close" 或 "next_open"
    ):
        """
        初始化回測引擎

        Args:
            initial_capital: 初始資金
            commission_rate: 手續費率（進出台幣的 %）
            position_size: 每次進場的資金比例
            execution_price: 交易執行價格模式
                - "close": 當根 K 線收盤價（會有 lookahead 風險）
                - "next_open": 下一根 K 線開盤價（更實際，避免 lookahead）
        """
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.position_size = position_size
        self.execution_price = execution_price

        # 運行時狀態
        self.current_capital = initial_capital
        self.position: Optional[Position] = None
        self.equity_history: List[dict] = []
        self.trades: List[Trade] = []

    def reset(self) -> None:
        """重置引擎狀態"""
        self.current_capital = self.initial_capital
        self.position = None
        self.equity_history = []
        self.trades = []

    def run(
        self,
        data: pd.DataFrame,
        signals: pd.DataFrame,
    ) -> BacktestResult:
        """
        執行回測

        Args:
            data: OHLCV 資料（必須包含 datetime, open, high, low, close）
            signals: 訊號資料（必須包含 datetime, signal）

        Returns:
            BacktestResult 物件

        Raises:
            ValueError: 資料格式錯誤時
        """
        # 驗證必要欄位
        required_data_cols = {"datetime", "open", "high", "low", "close"}
        if not required_data_cols.issubset(data.columns):
            raise ValueError(f"data 缺少必要欄位: {required_data_cols - set(data.columns)}")

        required_signal_cols = {"datetime", "signal"}
        if not required_signal_cols.issubset(signals.columns):
            raise ValueError(f"signals 缺少必要欄位: {required_signal_cols - set(signals.columns)}")

        # 合併資料
        df = data.merge(signals[["datetime", "signal"]], on="datetime", how="left")
        df = df.sort_values("datetime").reset_index(drop=True)

        # 重置狀態
        self.reset()

        # 執行回測
        for i in range(len(df) - 1):
            row = df.iloc[i]
            next_row = df.iloc[i + 1] if i + 1 < len(df) else None
            self._process_bar(row, next_row)

        # 記錄最終資產
        self._record_equity(df.iloc[-1])

        # 平倉（如果有持倉）
        if self.position is not None:
            self._close_position(
                exit_price=df.iloc[-1]["close"],
                exit_datetime=str(df.iloc[-1]["datetime"]),
            )

        # 計算結果
        result = self._calculate_result(df)

        return result

    def _process_bar(self, bar: pd.Series, next_bar: Optional[pd.Series] = None) -> None:
        """處理單根 K 線
        
        Args:
            bar: 當前 K 線
            next_bar: 下一根 K 線（用於 next_open 執行）
        """
        # 決定執行價格
        if self.execution_price == "next_open" and next_bar is not None:
            exec_price = next_bar["open"]
        else:
            exec_price = bar["close"]
        
        signal = bar.get("signal", 0)

        # 記錄當前資產（使用收盤價估值）
        self._record_equity(bar)

        # 處理訊號（使用執行價格）
        if signal == 1 and self.position is None:  # 買入訊號且無持倉
            self._open_position(
                entry_price=exec_price,
                entry_datetime=str(bar["datetime"]),
            )
        elif signal == -1 and self.position is not None:  # 賣出訊號且有持倉
            self._close_position(
                exit_price=exec_price,
                exit_datetime=str(bar["datetime"]),
            )

    def _open_position(
        self,
        entry_price: float,
        entry_datetime: str,
    ) -> None:
        """開倉"""
        # 計算可用資金
        available_capital = self.current_capital * self.position_size

        # 扣除手續費
        commission = available_capital * self.commission_rate
        actual_capital = available_capital - commission

        # 計算數量
        quantity = actual_capital / entry_price

        # 建立持倉
        self.position = Position(
            entry_datetime=entry_datetime,
            entry_price=entry_price,
            quantity=quantity,
            direction="long",
        )

        # 扣減資金
        self.current_capital -= available_capital

    def _close_position(
        self,
        exit_price: float,
        exit_datetime: str,
    ) -> None:
        """平倉"""
        if self.position is None:
            return

        # 計算賣出價值
        exit_value = self.position.quantity * exit_price

        # 扣除手續費
        commission = exit_value * self.commission_rate
        net_value = exit_value - commission

        # 計算損益
        entry_value = self.position.quantity * self.position.entry_price
        pnl = net_value - entry_value

        # 記錄交易
        trade = Trade(
            entry_datetime=self.position.entry_datetime,
            entry_price=self.position.entry_price,
            quantity=self.position.quantity,
            direction=self.position.direction,
            exit_datetime=exit_datetime,
            exit_price=exit_price,
            pnl=pnl,
            commission=commission,
        )
        self.trades.append(trade)

        # 還原資金 + 損益
        self.current_capital += net_value

        # 清除持倉
        self.position = None

    def _record_equity(self, bar: pd.Series) -> None:
        """記錄資產變化"""
        # 計算當前資產價值
        if self.position is not None:
            position_value = self.position.quantity * bar["close"]
        else:
            position_value = 0.0

        total_equity = self.current_capital + position_value

        self.equity_history.append({
            "datetime": bar["datetime"],
            "equity": total_equity,
            "capital": self.current_capital,
            "position_value": position_value,
            "has_position": self.position is not None,
        })

    def _calculate_result(self, df: pd.DataFrame) -> BacktestResult:
        """計算回測結果"""
        # 資產曲線
        equity_curve = pd.DataFrame(self.equity_history)

        # 基本統計
        final_equity = self.current_capital
        total_return = (final_equity - self.initial_capital) / self.initial_capital

        # 交易統計
        total_trades = len(self.trades)
        winning_trades = sum(1 for t in self.trades if t.pnl > 0)
        losing_trades = sum(1 for t in self.trades if t.pnl < 0)

        return BacktestResult(
            equity_curve=equity_curve,
            trades=self.trades,
            final_equity=final_equity,
            initial_capital=self.initial_capital,
            total_return=total_return,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
        )


def run_backtest(
    data: pd.DataFrame,
    signals: pd.DataFrame,
    initial_capital: float = 10000.0,
    commission_rate: float = 0.001,
    position_size: float = 1.0,
    execution_price: str = "close",
) -> BacktestResult:
    """
    便捷函數：執行回測

    Args:
        data: OHLCV 資料
        signals: 訊號資料
        initial_capital: 初始資金
        commission_rate: 手續費率
        position_size: 倉位比例
        execution_price: 交易執行價格模式 ("close" 或 "next_open")

    Returns:
        BacktestResult 物件
    """
    engine = BacktestEngine(
        initial_capital=initial_capital,
        commission_rate=commission_rate,
        position_size=position_size,
        execution_price=execution_price,
    )
    return engine.run(data, signals)
