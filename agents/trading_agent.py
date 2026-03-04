"""
Trading Agent - 交易执行 Agent

职责：
1. 接收风险管理决策
2. 执行交易（模拟或实盘）
3. 记录交易历史
4. 管理持仓
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, field
import pandas as pd


@dataclass
class Order:
    """订单"""
    symbol: str
    side: str  # "BUY" or "SELL"
    quantity: float
    price: float
    timestamp: datetime = field(default_factory=datetime.now)
    status: str = "pending"  # pending, filled, cancelled, failed
    order_id: Optional[str] = None


@dataclass
class Position:
    """持仓"""
    symbol: str
    quantity: float
    entry_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class TradingAgent:
    """
    Trading Agent - 交易执行
    
    职责：
    - 接收 Risk Agent 的决策
    - 执行实盘/模拟交易
    - 记录订单和持仓
    """
    
    def __init__(
        self,
        mode: str = "paper",  # "paper"=模拟, "live"=实盘
        initial_capital: float = 10000.0,
    ):
        """
        初始化 Trading Agent
        
        Args:
            mode: 交易模式 "paper" 或 "live"
            initial_capital: 初始资金
        """
        self.mode = mode
        self.initial_capital = initial_capital
        
        # 资金和持仓
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        
        # 订单历史
        self.orders: List[Order] = []
        self.trades: List[Dict[str, Any]] = []
        
        # 统计
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
    
    def execute_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
    ) -> Dict[str, Any]:
        """
        执行交易
        
        Args:
            symbol: 交易对
            side: 买入/卖出
            quantity: 数量
            price: 价格
            stop_loss: 止损比例
            take_profit: 止盈比例
            
        Returns:
            执行结果
        """
        order = Order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
        )
        
        try:
            # 模拟交易
            if self.mode == "paper":
                result = self._execute_paper(order)
            else:
                result = self._execute_live(order)
            
            # 记录订单
            self.orders.append(order)
            
            # 更新持仓
            if result["status"] == "filled":
                self._update_position(symbol, side, quantity, price)
                
                # 记录交易
                self.trades.append({
                    "timestamp": datetime.now(),
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "price": price,
                    "value": quantity * price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                })
                
                self.total_trades += 1
            
            return result
            
        except Exception as e:
            order.status = "failed"
            return {
                "status": "failed",
                "error": str(e),
                "order": order,
            }
    
    def _execute_paper(self, order: Order) -> Dict[str, Any]:
        """模拟交易执行"""
        # 检查资金
        if order.side == "BUY":
            required = order.quantity * order.price
            if required > self.cash:
                order.status = "cancelled"
                return {
                    "status": "cancelled",
                    "reason": "资金不足",
                    "order": order,
                }
        
        # 模拟成交
        order.status = "filled"
        
        return {
            "status": "filled",
            "order": order,
            "message": f"Paper trade {order.side} {order.quantity} {order.symbol} @ {order.price}",
        }
    
    def _execute_live(self, order: Order) -> Dict[str, Any]:
        """实盘交易执行（需要实现 Binance API）"""
        # TODO: 实现真实交易
        return {
            "status": "pending",
            "order": order,
            "message": "Live trading not implemented yet",
        }
    
    def _update_position(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
    ):
        """更新持仓"""
        if side == "BUY":
            if symbol in self.positions:
                # 加仓
                pos = self.positions[symbol]
                total_qty = pos.quantity + quantity
                new_price = (pos.entry_price * pos.quantity + price * quantity) / total_qty
                pos.quantity = total_qty
                pos.entry_price = new_price
            else:
                # 新建持仓
                self.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=quantity,
                    entry_price=price,
                    current_price=price,
                )
            
            # 扣减资金
            self.cash -= quantity * price
            
        elif side == "SELL":
            if symbol in self.positions:
                pos = self.positions[symbol]
                if pos.quantity >= quantity:
                    # 平仓
                    pnl = (price - pos.entry_price) * quantity
                    pos.realized_pnl += pnl
                    pos.quantity -= quantity
                    
                    if pos.quantity == 0:
                        del self.positions[symbol]
                    
                    # 收回资金
                    self.cash += quantity * price
                    
                    # 统计
                    if pnl > 0:
                        self.winning_trades += 1
                    else:
                        self.losing_trades += 1
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """获取持仓"""
        return self.positions.get(symbol)
    
    def update_prices(self, prices: Dict[str, float]):
        """更新当前价格（用于计算未实现盈亏）"""
        for symbol, price in prices.items():
            if symbol in self.positions:
                pos = self.positions[symbol]
                pos.current_price = price
                pos.unrealized_pnl = (price - pos.entry_price) * pos.quantity
    
    def get_portfolio_value(self) -> float:
        """获取投资组合总价值"""
        positions_value = sum(
            pos.quantity * pos.current_price
            for pos in self.positions.values()
        )
        return self.cash + positions_value
    
    def get_status(self) -> Dict[str, Any]:
        """获取 Agent 状态"""
        positions = {}
        for symbol, pos in self.positions.items():
            positions[symbol] = {
                "quantity": pos.quantity,
                "entry_price": pos.entry_price,
                "current_price": pos.current_price,
                "unrealized_pnl": pos.unrealized_pnl,
                "realized_pnl": pos.realized_pnl,
            }
        
        return {
            "mode": self.mode,
            "cash": round(self.cash, 2),
            "positions_value": round(sum(p.quantity * p.current_price for p in self.positions.values()), 2),
            "total_value": round(self.get_portfolio_value(), 2),
            "positions": positions,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.winning_trades / max(1, self.total_trades) * 100, 2) if self.total_trades > 0 else 0,
        }
    
    def reset(self):
        """重置 Agent"""
        self.cash = self.initial_capital
        self.positions = {}
        self.orders = []
        self.trades = []
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0


# ==================== 便捷函数 ====================

def create_trading_agent(
    mode: str = "paper",
    initial_capital: float = 10000.0,
) -> TradingAgent:
    """创建 Trading Agent"""
    return TradingAgent(mode=mode, initial_capital=initial_capital)
