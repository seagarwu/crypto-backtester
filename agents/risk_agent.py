"""
Risk Agent - 风险评估 Agent

职责：
1. 评估市场风险等级
2. 决定是否执行交易
3. 管理仓位大小
4. 设置止损止盈
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
import pandas as pd
import numpy as np


class RiskMetrics:
    """风险指标计算"""
    
    @staticmethod
    def calculate_volatility(returns: pd.Series, window: int = 20) -> float:
        """计算波动率"""
        if len(returns) < window:
            return 0.0
        return returns.tail(window).std() * 100
    
    @staticmethod
    def calculate_max_drawdown(prices: pd.Series) -> float:
        """计算最大回撤"""
        if len(prices) < 2:
            return 0.0
        cummax = prices.cummax()
        drawdown = (prices - cummax) / cummax
        return abs(drawdown.min()) * 100
    
    @staticmethod
    def calculate_var(returns: pd.Series, confidence: float = 0.95) -> float:
        """计算 VaR (Value at Risk)"""
        if len(returns) < 10:
            return 0.0
        return abs(returns.quantile(1 - confidence)) * 100


class RiskLevel:
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class RiskAgent:
    """
    Risk Agent - 风险管理
    
    职责：
    - 评估市场风险
    - 决定交易执行
    - 管理仓位
    - 设置止损止盈
    """
    
    def __init__(
        self,
        max_position_size: float = 1.0,  # 最大仓位 100%
        max_risk_per_trade: float = 0.02,  # 每笔交易最大风险 2%
        default_stop_loss: float = 0.05,  # 默认止损 5%
        default_take_profit: float = 0.10,  # 默认止盈 10%
    ):
        """
        初始化 Risk Agent
        
        Args:
            max_position_size: 最大仓位比例
            max_risk_per_trade: 每笔交易最大风险
            default_stop_loss: 默认止损比例
            default_take_profit: 默认止盈比例
        """
        self.max_position_size = max_position_size
        self.max_risk_per_trade = max_risk_per_trade
        self.default_stop_loss = default_stop_loss
        self.default_take_profit = default_take_profit
        
        # 当前状态
        self.current_risk_level = RiskLevel.MEDIUM
        self.portfolio_value = 10000.0
        self.current_position = 0.0
    
    def assess_market_risk(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        评估市场风险
        
        Args:
            data: 市场数据
            
        Returns:
            风险评估结果
        """
        if data is None or len(data) < 20:
            return {
                "risk_level": RiskLevel.MEDIUM,
                "volatility": 0,
                "drawdown": 0,
                "var": 0,
                "reason": "数据不足",
            }
        
        # 计算收益率
        returns = data["close"].pct_change().dropna()
        
        # 计算风险指标
        volatility = RiskMetrics.calculate_volatility(returns)
        max_dd = RiskMetrics.calculate_max_drawdown(data["close"])
        var_95 = RiskMetrics.calculate_var(returns)
        
        # 评估风险等级
        risk_level = self._determine_risk_level(
            volatility=volatility,
            max_drawdown=max_dd,
            var=var_95,
        )
        
        self.current_risk_level = risk_level
        
        return {
            "risk_level": risk_level,
            "volatility": round(volatility, 2),
            "max_drawdown": round(max_dd, 2),
            "var_95": round(var_95, 2),
            "recommendation": self._get_risk_recommendation(risk_level),
        }
    
    def _determine_risk_level(
        self,
        volatility: float,
        max_drawdown: float,
        var_95: float,
    ) -> str:
        """确定风险等级"""
        # 波动率 > 5% 或 最大回撤 > 20% = 高风险
        if volatility > 5 or max_drawdown > 20:
            return RiskLevel.HIGH
        
        # 波动率 > 3% 或 最大回撤 > 10% = 中高风险
        if volatility > 3 or max_drawdown > 10:
            return RiskLevel.MEDIUM
        
        # 波动率 > 1.5% = 中风险
        if volatility > 1.5:
            return RiskLevel.MEDIUM
        
        return RiskLevel.LOW
    
    def _get_risk_recommendation(self, risk_level: str) -> Dict[str, Any]:
        """获取风险建议"""
        recommendations = {
            RiskLevel.LOW: {
                "action": "normal",
                "position_multiplier": 1.0,
                "stop_loss": self.default_stop_loss,
                "take_profit": self.default_take_profit * 1.5,  # 可追求更多利润
            },
            RiskLevel.MEDIUM: {
                "action": "caution",
                "position_multiplier": 0.7,
                "stop_loss": self.default_stop_loss * 0.8,  # 缩小止损
                "take_profit": self.default_take_profit,
            },
            RiskLevel.HIGH: {
                "action": "reduce",
                "position_multiplier": 0.3,
                "stop_loss": self.default_stop_loss * 0.5,
                "take_profit": self.default_take_profit * 0.5,
            },
            RiskLevel.EXTREME: {
                "action": "avoid",
                "position_multiplier": 0,
                "stop_loss": 0,
                "take_profit": 0,
            },
        }
        return recommendations.get(risk_level, recommendations[RiskLevel.MEDIUM])
    
    def evaluate_trade(
        self,
        signal: int,  # 1=buy, -1=sell, 0=hold
        market_data: pd.DataFrame,
        strategy_metrics: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        评估是否执行交易
        
        Args:
            signal: 交易信号
            market_data: 市场数据
            strategy_metrics: 策略指标
            
        Returns:
            交易决策结果
        """
        # 评估市场风险
        risk_assessment = self.assess_market_risk(market_data)
        risk_level = risk_assessment["risk_level"]
        recommendation = risk_assessment["recommendation"]
        
        # 如果信号为 hold，直接返回
        if signal == 0:
            return {
                "action": "HOLD",
                "reason": "无交易信号",
                "risk_level": risk_level,
                "position_size": 0,
            }
        
        # 风险过大，不执行交易
        if risk_level == RiskLevel.HIGH:
            return {
                "action": "REJECT",
                "reason": f"市场风险过高 ({risk_level})",
                "risk_level": risk_level,
                "position_size": 0,
                "risk_assessment": risk_assessment,
            }
        
        if risk_level == RiskLevel.EXTREME:
            return {
                "action": "REJECT",
                "reason": "市场极端风险，禁止交易",
                "risk_level": risk_level,
                "position_size": 0,
                "risk_assessment": risk_assessment,
            }
        
        # 计算仓位
        base_position = self.max_position_size
        multiplier = recommendation["position_multiplier"]
        position_size = base_position * multiplier
        
        # 如果策略有高回撤，降低仓位
        if strategy_metrics:
            strategy_dd = strategy_metrics.get("max_drawdown", 0)
            if strategy_dd > 15:
                position_size *= 0.5
            elif strategy_dd > 10:
                position_size *= 0.7
        
        # 决定执行
        action = "BUY" if signal == 1 else "SELL"
        
        return {
            "action": action,
            "reason": f"信号: {signal}, 风险: {risk_level}",
            "risk_level": risk_level,
            "position_size": round(position_size, 4),
            "stop_loss": recommendation["stop_loss"],
            "take_profit": recommendation["take_profit"],
            "risk_assessment": risk_assessment,
        }
    
    def update_portfolio(self, value: float, position: float = 0):
        """更新投资组合状态"""
        self.portfolio_value = value
        self.current_position = position
    
    def get_status(self) -> Dict[str, Any]:
        """获取 Agent 状态"""
        return {
            "risk_level": self.current_risk_level,
            "portfolio_value": self.portfolio_value,
            "current_position": self.current_position,
            "max_position_size": self.max_position_size,
            "max_risk_per_trade": self.max_risk_per_trade,
        }


# ==================== 便捷函数 ====================

def create_risk_agent(
    max_position_size: float = 1.0,
    max_risk_per_trade: float = 0.02,
) -> RiskAgent:
    """创建 Risk Agent"""
    return RiskAgent(
        max_position_size=max_position_size,
        max_risk_per_trade=max_risk_per_trade,
    )
