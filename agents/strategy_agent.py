"""
Strategy Agent - 策略信号产生 Agent

职责：
1. 使用历史数据和技术指标产生交易信号
2. 多策略评估和选择
3. 与 Market Monitor Agent 协作获取数据
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import pandas as pd
import numpy as np

from strategies.base import BaseStrategy
from strategies.ma_crossover import MACrossoverStrategy
from backtest import run_backtest
from metrics import calculate_metrics

logger = logging.getLogger(__name__)


class StrategySelector:
    """策略选择器"""
    
    def __init__(self):
        self.strategies: Dict[str, BaseStrategy] = {}
        self.register_default_strategies()
    
    def register_default_strategies(self):
        """注册默认策略"""
        # MA Cross
        self.register("ma_cross_10_50", MACrossoverStrategy(short_window=10, long_window=50))
        self.register("ma_cross_20_50", MACrossoverStrategy(short_window=20, long_window=50))
        self.register("ma_cross_20_100", MACrossoverStrategy(short_window=20, long_window=100))
        self.register("ma_cross_50_200", MACrossoverStrategy(short_window=50, long_window=200))
    
    def register(self, name: str, strategy: BaseStrategy):
        """注册策略"""
        self.strategies[name] = strategy
    
    def get(self, name: str) -> Optional[BaseStrategy]:
        """获取策略"""
        return self.strategies.get(name)
    
    def list_strategies(self) -> List[str]:
        """列出所有策略"""
        return list(self.strategies.keys())


class StrategyAgent:
    """
    Strategy Agent - 策略信号产生
    
    职责：
    - 加载市场数据
    - 运行多个策略
    - 选择最佳策略
    - 产生交易信号
    """
    
    def __init__(
        self,
        data_source=None,  # MarketMonitorAgent 或 callable
        initial_capital: float = 10000.0,
        commission_rate: float = 0.001,
    ):
        """
        初始化 Strategy Agent
        
        Args:
            data_source: 数据源（MarketMonitorAgent 或函数）
            initial_capital: 初始资金
            commission_rate: 手续费率
        """
        self.data_source = data_source
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        
        self.selector = StrategySelector()
        
        # 当前状态
        self.current_signals: Dict[str, Any] = {}
        self.strategy_results: Dict[str, Dict[str, Any]] = {}
        self.best_strategy: Optional[str] = None
    
    def set_data_source(self, data_source):
        """设置数据源"""
        self.data_source = data_source
    
    def run_strategy(
        self,
        strategy_name: str,
        data: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        运行单个策略
        
        Args:
            strategy_name: 策略名称
            data: 市场数据
            
        Returns:
            策略结果（含信号和指标）
        """
        strategy = self.selector.get(strategy_name)
        if strategy is None:
            return {"error": f"Strategy {strategy_name} not found"}
        
        try:
            # 产生信号
            signals = strategy.on_data(data)
            
            # 运行回测
            result = run_backtest(
                data=data,
                signals=signals,
                initial_capital=self.initial_capital,
                commission_rate=self.commission_rate,
            )
            
            # 计算指标
            metrics = calculate_metrics(result)
            
            return {
                "strategy": strategy_name,
                "signals": signals,
                "result": result,
                "metrics": metrics,
                "total_return": metrics.get("total_return", 0),
                "sharpe_ratio": metrics.get("sharpe_ratio", 0),
                "max_drawdown": metrics.get("max_drawdown", 0),
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def run_all_strategies(
        self,
        data: pd.DataFrame,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        运行所有策略并排序
        
        Args:
            data: 市场数据
            top_k: 返回 Top K 策略
            
        Returns:
            排序后的策略结果列表
        """
        results = []
        
        for strategy_name in self.selector.list_strategies():
            result = self.run_strategy(strategy_name, data)
            if "error" not in result:
                results.append(result)
        
        # 按 Sharpe Ratio 排序
        results.sort(key=lambda x: x.get("sharpe_ratio", 0), reverse=True)
        
        # 保存结果
        self.strategy_results = {r["strategy"]: r for r in results}
        
        # 选最佳策略
        if results:
            self.best_strategy = results[0]["strategy"]
            self.current_signals = results[0].get("signals", {})
        
        return results[:top_k]
    
    def get_signal(
        self,
        symbol: str,
        interval: str = "1h",
    ) -> Dict[str, Any]:
        """
        获取交易信号
        
        Args:
            symbol: 交易对
            interval: K线间隔
            
        Returns:
            信号结果
        """
        # 获取数据
        data = self._load_data(symbol, interval)
        
        if data is None or data.empty:
            return {"error": "No data available"}
        
        # 运行策略
        top_results = self.run_all_strategies(data)
        
        if not top_results:
            return {"error": "No valid strategy results"}
        
        best = top_results[0]
        
        # 获取最新信号
        latest_signal = 0
        if not best["signals"].empty:
            latest_signal = int(best["signals"].iloc[-1].get("signal", 0))
        
        return {
            "symbol": symbol,
            "interval": interval,
            "best_strategy": best["strategy"],
            "signal": latest_signal,  # 1=buy, -1=sell, 0=hold
            "signal_text": {1: "BUY", -1: "SELL", 0: "HOLD"}[latest_signal],
            "metrics": {
                "total_return": best.get("total_return", 0),
                "sharpe_ratio": best.get("sharpe_ratio", 0),
                "max_drawdown": best.get("max_drawdown", 0),
            },
            "all_strategies": [
                {
                    "name": r["strategy"],
                    "sharpe": r.get("sharpe_ratio", 0),
                    "return": r.get("total_return", 0),
                }
                for r in top_results
            ],
            "data_time": str(data["datetime"].max()) if "datetime" in data.columns else None,
        }
    
    def _load_data(self, symbol: str, interval: str) -> Optional[pd.DataFrame]:
        """加载数据"""
        if self.data_source is None:
            return None
        
        # 如果是 MarketMonitorAgent
        if hasattr(self.data_source, "get_latest_data"):
            return self.data_source.get_latest_data(symbol, interval)
        
        # 如果是函数
        if callable(self.data_source):
            return self.data_source(symbol, interval)
        
        return None
    
    def add_strategy(self, name: str, strategy: BaseStrategy):
        """添加自定义策略"""
        self.selector.register(name, strategy)
    
    def get_status(self) -> Dict[str, Any]:
        """获取 Agent 状态"""
        return {
            "strategies": self.selector.list_strategies(),
            "best_strategy": self.best_strategy,
            "results_count": len(self.strategy_results),
        }


# ==================== 便捷函数 ====================

def create_strategy_agent(
    data_source=None,
    initial_capital: float = 10000.0,
) -> StrategyAgent:
    """创建 Strategy Agent"""
    return StrategyAgent(
        data_source=data_source,
        initial_capital=initial_capital,
    )
