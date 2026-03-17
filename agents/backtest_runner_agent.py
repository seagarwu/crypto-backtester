#!/usr/bin/env python3
"""
Backtest Runner Agent - 回測執行 Agent

職責：
- 加載策略和數據
- 執行回測
- 返回詳細的回測結果
"""

import os
import sys
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
from pathlib import Path
import importlib.util

import pandas as pd
import numpy as np

# 確保可以匯入模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.agent_prompting import build_agent_context
from backtest.engine import BacktestEngine, BacktestResult
from strategies.ma_crossover import MACrossoverStrategy

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """回測配置"""
    symbol: str = "BTCUSDT"
    interval: str = "1h"
    start_date: str = "2023-01-01"
    end_date: str = "2024-12-31"
    initial_capital: float = 10000.0
    commission_rate: float = 0.001
    position_size: float = 1.0


@dataclass
class BacktestReport:
    """回測報告"""
    strategy_name: str
    config: BacktestConfig
    
    # 收益指標
    total_return: float = 0.0
    annual_return: float = 0.0
    
    # 風險指標
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    volatility: float = 0.0
    
    # 交易統計
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    
    # 平均交易
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    
    # 時間
    backtest_duration_days: int = 0
    
    # 詳情
    trades: List[Dict[str, Any]] = field(default_factory=list)
    equity_curve: pd.DataFrame = None


class BacktestRunnerAgent:
    """
    回測執行 Agent
    
    負責：
    1. 加載市場數據
    2. 加載策略
    3. 執行回測
    4. 生成報告
    """
    
    def __init__(
        self,
        data_dir: str = None,
    ):
        # 使用專案根目錄
        if data_dir is None:
            project_root = Path(__file__).parent.parent
            data_dir = str(project_root / "data")
        self.data_dir = data_dir
        self.agent_context = build_agent_context("backtest_agent")
        
        # 嘗試載入策略
        self.strategies = self._discover_strategies()
    
    def _discover_strategies(self) -> Dict[str, Any]:
        """發現可用策略"""
        strategies = {}
        
        # 使用專案根目錄
        project_root = Path(__file__).parent.parent
        strategies_dir = project_root / "strategies"
        
        if not strategies_dir.exists():
            return strategies
        
        for file in strategies_dir.glob("*.py"):
            if file.stem in ["__init__", "base"]:
                continue
            
            try:
                # 動態載入模組
                spec = importlib.util.spec_from_file_location(
                    file.stem, 
                    file
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # 找尋策略類別
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) 
                        and hasattr(attr, "__bases__")
                        and "BaseStrategy" in [b.__name__ for b in attr.__bases__]):
                        strategies[file.stem] = attr
                        
            except Exception as e:
                logger.debug(f"載入策略 {file.stem}: {e}")
        
        return strategies
    
    def load_data(
        self,
        symbol: str,
        interval: str,
        start_date: str = None,
        end_date: str = None,
    ) -> pd.DataFrame:
        """
        加載市場數據
        
        支援兩種格式：
        1. data/{symbol}_{interval}.csv (舊格式)
        2. data/{interval}/{symbol}_{interval}_{yearmonth}.csv (新月格式)
        """
        # 嘗試新月格式
        interval_dir = Path(self.data_dir) / interval
        if interval_dir.exists():
            # 找出所有匹配的月份檔案
            pattern = f"{symbol}_{interval}_*.csv"
            files = sorted(interval_dir.glob(pattern))
            
            if files:
                dfs = []
                for f in files:
                    df = pd.read_csv(f, parse_dates=['datetime'])
                    dfs.append(df)
                
                if dfs:
                    data = pd.concat(dfs, ignore_index=True)
                    data = data.drop_duplicates(subset=['datetime'], keep='first')
                    data = data.sort_values('datetime').reset_index(drop=True)
                    
                    # 篩選日期範圍
                    if start_date:
                        data = data[data['datetime'] >= pd.to_datetime(start_date)]
                    if end_date:
                        data = data[data['datetime'] <= pd.to_datetime(end_date)]
                    
                    return data
        
        # 嘗試舊格式
        old_file = Path(self.data_dir) / f"{symbol}_{interval}.csv"
        if old_file.exists():
            data = pd.read_csv(old_file, parse_dates=['datetime'])
            
            if start_date:
                data = data[data['datetime'] >= pd.to_datetime(start_date)]
            if end_date:
                data = data[data['datetime'] <= pd.to_datetime(end_date)]
            
            return data
        
        raise FileNotFoundError(f"找不到數據: {symbol} {interval}")
    
    def run_backtest(
        self,
        strategy_name: str,
        strategy_class: Any = None,
        strategy_params: Dict[str, Any] = None,
        config: BacktestConfig = None,
    ) -> BacktestReport:
        """
        執行回測
        
        Args:
            strategy_name: 策略名稱
            strategy_class: 策略類別 (可選)
            strategy_params: 策略參數
            config: 回測配置
            
        Returns:
            BacktestReport: 回測報告
        """
        config = config or BacktestConfig()
        strategy_params = strategy_params or {}
        
        # 載入數據
        logger.info(f"載入數據: {config.symbol} {config.interval}")
        data = self.load_data(
            config.symbol,
            config.interval,
            config.start_date,
            config.end_date,
        )
        
        if data.empty:
            raise ValueError("數據為空")
        
        # 如果沒有提供策略類別，嘗試從已發現的策略中獲取
        if strategy_class is None:
            if strategy_name in self.strategies:
                strategy_class = self.strategies[strategy_name]
            else:
                # 使用預設的 MA Crossover
                strategy_class = MACrossoverStrategy
        
        # 實例化策略
        strategy = strategy_class(**strategy_params)
        
        # 計算指標
        logger.info(f"計算指標...")
        indicators = self._calculate_indicators(strategy, data)
        
        # 生成信號
        logger.info(f"生成信號...")
        signals = strategy.generate_signals(data)
        
        # 確保信號是 DataFrame
        if isinstance(signals, dict):
            signals = pd.DataFrame(signals)
        
        # 確保必要的欄位
        if 'datetime' not in signals.columns and 'datetime' in data.columns:
            signals['datetime'] = data['datetime'].values
        
        # 執行回測
        logger.info(f"執行回測...")
        engine = BacktestEngine(
            initial_capital=config.initial_capital,
            commission_rate=config.commission_rate,
            position_size=config.position_size,
            execution_price="next_open",
        )
        
        result = engine.run(data, signals)
        
        # 生成報告
        return self._generate_report(strategy_name, config, result, data)
    
    def _calculate_indicators(self, strategy, data: pd.DataFrame) -> Dict[str, pd.Series]:
        """計算策略所需的指標"""
        indicators = {}
        
        required = strategy.required_indicators
        
        for ind in required:
            if ind.startswith("Volume_MA_"):
                period = int(ind.split("_")[2])
                indicators[ind] = data['volume'].rolling(window=period).mean()

            elif ind.startswith("MA_"):
                # 移動平均
                period = int(ind.split("_")[1])
                indicators[ind] = data['close'].rolling(window=period).mean()
            
            elif ind.startswith("EMA_"):
                # 指數移動平均
                period = int(ind.split("_")[1])
                indicators[ind] = data['close'].ewm(span=period, adjust=False).mean()
            
            elif ind.startswith("RSI_"):
                # RSI
                period = int(ind.split("_")[1])
                delta = data['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
                rs = gain / loss
                indicators[ind] = 100 - (100 / (1 + rs))
            
            elif ind.startswith("MACD"):
                # MACD
                ema12 = data['close'].ewm(span=12, adjust=False).mean()
                ema26 = data['close'].ewm(span=26, adjust=False).mean()
                macd = ema12 - ema26
                signal = macd.ewm(span=9, adjust=False).mean()
                histogram = macd - signal
                indicators[ind] = histogram
            
            elif ind.startswith("BB_") or ind.startswith("BBand_"):
                # Bollinger Bands
                parts = ind.split("_")
                period = int(parts[1])
                std_mult = float(parts[2]) if len(parts) > 2 else 2.0
                
                sma = data['close'].rolling(window=period).mean()
                std = data['close'].rolling(window=period).std()
                
                upper = sma + (std * std_mult)
                lower = sma - (std * std_mult)
                
                indicators[f"{ind}_upper"] = upper
                indicators[f"{ind}_middle"] = sma
                indicators[f"{ind}_lower"] = lower
            
            else:
                # 未知指標，假設是簡單的收盤價
                indicators[ind] = data['close']
        
        return indicators
    
    def _generate_report(
        self,
        strategy_name: str,
        config: BacktestConfig,
        result: BacktestResult,
        data: pd.DataFrame,
    ) -> BacktestReport:
        """生成回測報告"""
        
        # 計算收益率序列
        equity = result.equity_curve.set_index('datetime')['equity'] if 'equity' in result.equity_curve.columns else pd.Series(result.final_equity)
        
        # 計算指標
        returns = equity.pct_change().dropna()
        
        # Sharpe Ratio (年化)
        if len(returns) > 0 and returns.std() > 0:
            sharpe = returns.mean() / returns.std() * np.sqrt(252 * 24)  # 假設 1h 數據
        else:
            sharpe = 0.0
        
        # 最大回撤
        cummax = equity.cummax()
        drawdown = (equity - cummax) / cummax
        max_drawdown = abs(drawdown.min()) * 100
        
        # 波動率 (年化)
        volatility = returns.std() * np.sqrt(252 * 24) * 100 if len(returns) > 0 else 0
        
        # 交易統計
        total_trades = result.total_trades
        winning = result.winning_trades
        losing = result.losing_trades
        win_rate = (winning / total_trades * 100) if total_trades > 0 else 0
        
        # 平均勝敗
        if winning > 0:
            wins = [t.pnl for t in result.trades if t.pnl > 0]
            avg_win = np.mean(wins) if wins else 0
        else:
            avg_win = 0
            
        if losing > 0:
            losses = [t.pnl for t in result.trades if t.pnl < 0]
            avg_loss = np.mean(losses) if losses else 0
        else:
            avg_loss = 0
        
        # Profit Factor
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        
        # 回測天數
        if len(data) > 0:
            start_dt = pd.to_datetime(data['datetime'].iloc[0])
            end_dt = pd.to_datetime(data['datetime'].iloc[-1])
            days = (end_dt - start_dt).days
        else:
            days = 0
        
        # 年化收益
        if days > 0:
            annual_return = (result.final_equity / result.initial_capital) ** (365 / days) - 1
        else:
            annual_return = 0
        
        # 總收益
        total_return = (result.final_equity / result.initial_capital - 1) * 100
        
        # 轉換交易記錄
        trades_list = []
        for t in result.trades:
            trades_list.append({
                'entry_datetime': t.entry_datetime,
                'exit_datetime': t.exit_datetime,
                'entry_price': t.entry_price,
                'exit_price': t.exit_price,
                'pnl': t.pnl,
                'commission': t.commission,
            })
        
        return BacktestReport(
            strategy_name=strategy_name,
            config=config,
            total_return=total_return,
            annual_return=annual_return * 100,
            sharpe_ratio=sharpe,
            max_drawdown=max_drawdown,
            volatility=volatility,
            total_trades=total_trades,
            winning_trades=winning,
            losing_trades=losing,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            backtest_duration_days=days,
            trades=trades_list,
            equity_curve=result.equity_curve,
        )
    
    def get_available_strategies(self) -> List[str]:
        """獲取可用策略列表"""
        return list(self.strategies.keys())


# 便捷函數
def create_backtest_runner(data_dir: str = "data") -> BacktestRunnerAgent:
    """建立回測執行 Agent"""
    return BacktestRunnerAgent(data_dir=data_dir)


__all__ = [
    "BacktestRunnerAgent",
    "BacktestConfig",
    "BacktestReport",
    "create_backtest_runner",
]
