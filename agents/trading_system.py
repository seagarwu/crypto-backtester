"""
Trading System - 多 Agent 协调系统

整合：
- Market Monitor Agent (数据获取)
- Strategy Agent (策略信号)
- Risk Agent (风险管理)
- Trading Agent (交易执行)
"""

from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
import pandas as pd
import threading
import time

from .market_monitor_agent import MarketMonitorAgent
from .strategy_agent import StrategyAgent
from .risk_agent import RiskAgent
from .trading_agent import TradingAgent


class TradingSystem:
    """
    Trading System - 多 Agent 交易系统
    
    协调所有 Agent 的工作流程：
    1. Market Monitor 抓取数据
    2. Strategy Agent 产生信号
    3. Risk Agent 评估风险
    4. Trading Agent 执行交易
    """
    
    def __init__(
        self,
        symbols: List[str] = None,
        intervals: List[str] = ["1h"],
        initial_capital: float = 10000.0,
        mode: str = "paper",  # "paper" or "live"
        fetch_interval_minutes: int = 60,
    ):
        """
        初始化交易系统
        
        Args:
            symbols: 交易对列表
            intervals: K线间隔
            initial_capital: 初始资金
            mode: 交易模式
            fetch_interval_minutes: 数据抓取间隔
        """
        self.symbols = symbols or ["BTCUSDT"]
        self.intervals = intervals
        self.initial_capital = initial_capital
        self.mode = mode
        
        # 初始化所有 Agents
        self.market_monitor = MarketMonitorAgent(
            symbols=self.symbols,
            intervals=self.intervals,
            fetch_interval_minutes=fetch_interval_minutes,
        )
        
        self.strategy_agent = StrategyAgent(
            data_source=self.market_monitor,
            initial_capital=initial_capital,
        )
        
        self.risk_agent = RiskAgent()
        
        self.trading_agent = TradingAgent(
            mode=mode,
            initial_capital=initial_capital,
        )
        
        # 状态
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.cycle_history: List[Dict[str, Any]] = []
        
        # 回调
        self.on_trade: Optional[Callable] = None
        self.on_signal: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
    
    def start(self) -> None:
        """启动交易系统"""
        if self._running:
            print("⚠️ 系统已在运行")
            return
        
        print("🚀 启动交易系统...")
        
        # 注册数据回调
        self.market_monitor.register_callback(self._on_new_data)
        
        # 启动数据监控
        self.market_monitor.start()
        
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        
        print("✅ 交易系统已启动")
    
    def stop(self) -> None:
        """停止交易系统"""
        print("🛑 停止交易系统...")
        
        self._running = False
        self.market_monitor.stop()
        
        if self._thread:
            self._thread.join(timeout=5)
        
        print("✅ 系统已停止")
    
    def run_once(self) -> Dict[str, Any]:
        """
        执行一次完整的交易流程
        
        Returns:
            执行结果
        """
        results = {}
        
        for symbol in self.symbols:
            for interval in self.intervals:
                try:
                    result = self._process_symbol(symbol, interval)
                    results[f"{symbol}_{interval}"] = result
                except Exception as e:
                    print(f"❌ 处理 {symbol} {interval} 失败: {e}")
                    results[f"{symbol}_{interval}"] = {"error": str(e)}
        
        return results
    
    def _process_symbol(self, symbol: str, interval: str) -> Dict[str, Any]:
        """处理单个交易对"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "interval": interval,
        }
        
        # 1. 获取数据
        data = self.market_monitor.get_latest_data(symbol, interval)
        
        if data is None or data.empty:
            result["status"] = "no_data"
            return result
        
        result["data_rows"] = len(data)
        
        # 2. Strategy Agent 产生信号
        signal_result = self.strategy_agent.get_signal(symbol, interval)
        
        result["signal"] = signal_result.get("signal", 0)
        result["signal_text"] = signal_result.get("signal_text", "HOLD")
        result["best_strategy"] = signal_result.get("best_strategy")
        result["strategy_metrics"] = signal_result.get("metrics", {})
        
        # 回调
        if self.on_signal:
            self.on_signal(symbol, signal_result)
        
        # 3. Risk Agent 评估
        risk_result = self.risk_agent.evaluate_trade(
            signal=signal_result.get("signal", 0),
            market_data=data,
            strategy_metrics=signal_result.get("metrics", {}),
        )
        
        result["risk_action"] = risk_result.get("action")
        result["risk_level"] = risk_result.get("risk_level")
        result["position_size"] = risk_result.get("position_size", 0)
        
        # 4. 执行交易
        if risk_result.get("action") in ["BUY", "SELL"]:
            # 获取当前价格
            current_price = float(data["close"].iloc[-1])
            
            # 更新投资组合价值
            self.risk_agent.update_portfolio(
                value=self.trading_agent.get_portfolio_value(),
            )
            
            # 执行交易
            trade_result = self.trading_agent.execute_trade(
                symbol=symbol,
                side=risk_result["action"],
                quantity=risk_result.get("position_size", 0) * self.initial_capital / current_price,
                price=current_price,
                stop_loss=risk_result.get("stop_loss", 0),
                take_profit=risk_result.get("take_profit", 0),
            )
            
            result["trade"] = trade_result
            
            # 回调
            if self.on_trade:
                self.on_trade(symbol, trade_result)
        
        result["status"] = "completed"
        
        # 5. 记录到历史
        self.cycle_history.append(result)
        
        return result
    
    def _on_new_data(self, symbol: str, df: pd.DataFrame):
        """新数据回调"""
        print(f"📊 收到新数据: {symbol} ({len(df)} 行)")
        
        # 可以选择立即处理
        # self._process_symbol(symbol, "1h")
    
    def _run_loop(self):
        """运行循环"""
        while self._running:
            # 执行一次完整流程
            self.run_once()
            
            # 等待下一次
            # 实际间隔由 Market Monitor 控制
            time.sleep(60)
    
    def get_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            "running": self._running,
            "symbols": self.symbols,
            "mode": self.mode,
            "market_monitor": self.market_monitor.get_market_summary(),
            "strategy_agent": self.strategy_agent.get_status(),
            "risk_agent": self.risk_agent.get_status(),
            "trading_agent": self.trading_agent.get_status(),
            "cycles": len(self.cycle_history),
        }
    
    def get_trade_history(self) -> List[Dict[str, Any]]:
        """获取交易历史"""
        return self.trading_agent.trades
    
    def get_cycle_history(self) -> List[Dict[str, Any]]:
        """获取执行周期历史"""
        return self.cycle_history


# ==================== 便捷函数 ====================

def create_trading_system(
    symbols: List[str] = None,
    intervals: List[str] = ["1h"],
    initial_capital: float = 10000.0,
    mode: str = "paper",
) -> TradingSystem:
    """创建交易系统"""
    return TradingSystem(
        symbols=symbols,
        intervals=intervals,
        initial_capital=initial_capital,
        mode=mode,
    )
