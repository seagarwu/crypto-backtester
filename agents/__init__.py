"""多智能體系統 - Agent 工廠與基礎設施"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import os

# LangGraph imports
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openrouter import ChatOpenRouter

# Market Monitor Agent
from .market_monitor_agent import MarketMonitorAgent, MarketDataManager, create_market_monitor

# Strategy Agent
from .strategy_agent import StrategyAgent, StrategySelector, create_strategy_agent

# Risk Agent
from .risk_agent import RiskAgent, RiskLevel, create_risk_agent

# Trading Agent
from .trading_agent import TradingAgent, Order, Position, create_trading_agent

# Trading System
from .trading_system import TradingSystem, create_trading_system


class AgentRole(Enum):
    """Agent 角色定義"""
    MARKET_MONITOR = "market_monitor"      # 市場監控
    RISK_MANAGER = "risk_manager"          # 風險管理
    STRATEGY_DEVELOPER = "strategy_dev"   # 策略開發
    BACKTESTER = "backtester"              # 回測
    ENGINEER = "engineer"                  # 工程
    REPORTER = "reporter"                  # 彙報


@dataclass
class AgentConfig:
    """Agent 配置"""
    role: AgentRole
    model: str = "minimax/minimax-chat"  # MiniMax model
    temperature: float = 0.7
    max_tokens: int = 2000
    system_prompt: str = ""


@dataclass
class TradingState:
    """共享狀態 - 所有 Agent 可訪問的數據"""
    # 市場數據
    current_price: float = 0.0
    market_data: Dict[str, Any] = field(default_factory=dict)
    
    # 策略相關
    active_strategy: Optional[str] = None
    strategy_params: Dict[str, Any] = field(default_factory=dict)
    
    # 風險管理
    risk_level: str = "medium"  # low, medium, high
    position_size: float = 0.0
    portfolio_value: float = 10000.0
    
    # 決策
    signal: Optional[str] = None  # buy, sell, hold
    confidence: float = 0.0
    
    # 訊息歷史
    messages: List[Dict[str, str]] = field(default_factory=list)
    
    # 報告
    report: str = ""


def get_llm(config: AgentConfig):
    """建立 LLM 實例"""
    return ChatOpenRouter(
        model_name=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", "")
    )


# Agent Prompt 模板
AGENT_PROMPTS = {
    AgentRole.MARKET_MONITOR: """你是一個專業的加密貨幣市場監控分析師。

你的職責：
- 實時監控市場數據（價格、成交量、訂單簿）
- 識別市場趨勢和模式
- 提供清晰的市場狀態報告

市場數據來源：{market_source}

請根據最新數據提供：
1. 當前市場趨勢（多頭/空頭/盤整）
2. 關鍵技術指標狀態
3. 異常波動警告
4. 短期價格預測""",

    AgentRole.RISK_MANAGER: """你是一個專業的風險管理專家。

你的職責：
- 評估交易風險
- 決定是否執行交易
- 管理倉位大小
- 設置止損止盈

當前投資組合：
- 總價值: ${portfolio_value}
- 風險等級: {risk_level}
- 當前倉位: {position_size}

市場狀態：{market_state}

請提供：
1. 風險評估（1-10分）
2. 建議倉位大小
3. 止損/止盈建議
4. 交易決定（買/賣/持有）""",

    AgentRole.STRATEGY_DEVELOPER: """你是一個量化策略開發專家。

你的職責：
- 根據市場狀況設計交易策略
- 優化策略參數
- 識別新的交易機會

現有策略：{existing_strategies}
市場環境：{market_state}

請提供：
1. 策略建議
2. 參數優化建議
3. 風險調整後的預期收益""",

    AgentRole.BACKTESTER: """你是一個回測專家。

你的職責：
- 測試交易策略的歷史表現
- 計算關鍵指標（Sharpe, Drawdown, Win Rate）
- 提供改進建議

待測試策略：{strategy}
回測期間：{timeframe}

請提供：
1. 回測結果摘要
2. 關鍵指標
3. 策略評估""",

    AgentRole.ENGINEER: """你是一個程式碼工程師。

你的職責：
- 實現交易策略代碼
- 確保代碼品質
- 編寫測試

需求：{requirement}

請提供：
1. 代碼實現
2. 測試用例
3. 文檔說明""",

    AgentRole.REPORTER: """你是一個投資組合經理助手。

你的職責：
- 彙總各Agent的分析結果
- 生成人類可讀的報告
- 突出關鍵決策點

數據來源：
{agent_results}

請生成：
1. 執行摘要
2. 詳細分析
3. 建議行動""",
}


__all__ = [
    # Core
    "AgentRole",
    "AgentConfig",
    "TradingState",
    "get_llm",
    "AGENT_PROMPTS",
    # Market Monitor
    "MarketMonitorAgent",
    "MarketDataManager",
    "create_market_monitor",
    # Strategy
    "StrategyAgent",
    "StrategySelector",
    "create_strategy_agent",
    # Risk
    "RiskAgent",
    "RiskLevel",
    "create_risk_agent",
    # Trading
    "TradingAgent",
    "Order",
    "Position",
    "create_trading_agent",
    # System
    "TradingSystem",
    "create_trading_system",
]
