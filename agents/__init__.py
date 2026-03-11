"""多智能體系統 - Agent 工廠與基礎設施"""

import logging
import sys
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import os

# 設置日誌格式
def setup_logging(level: int = logging.INFO):
    """設置全局日誌"""
    logging.basicConfig(
        level=level,
        format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%H:%M:%S',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    return logging.getLogger(__name__)

# 預設日誌
logger = setup_logging()

# LangGraph imports
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openrouter import ChatOpenRouter

# Core imports
from core.llm_manager import (
    LLMManager,
    get_llm_manager,
    get_llm,
    get_llm_for_task,
    recommend_model,
    AVAILABLE_MODELS,
    TASK_MODEL_MAPPING,
)

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

# Strategy R&D
from .strategy_developer_agent import StrategyDeveloperAgent, StrategySpec, create_strategy_developer
from .backtest_runner_agent import BacktestRunnerAgent, BacktestConfig, BacktestReport, create_backtest_runner
from .strategy_evaluator_agent import StrategyEvaluatorAgent, EvaluationMetrics, EvaluationResult, StrategyEvaluation, create_strategy_evaluator
from .reporter_agent import ReporterAgent, StrategyReport, create_reporter
from .strategy_rd_workflow import StrategyRDWorkflow, RDConfig


# ==================== Agent 默認模型配置 ====================

# 根據 Agent 類型，預設推薦的模型
AGENT_DEFAULT_MODELS = {
    "market_monitor": {
        "model": "MiniMax-M2.5",
        "task": "market_analysis",
        "reason": "快速理解市場數據，成本低",
    },
    "strategy": {
        "model": "MiniMax-M2.5",
        "task": "strategy_development",
        "reason": "創意和技術能力",
    },
    "risk": {
        "model": "MiniMax-M2.5",
        "task": "risk_assessment",
        "reason": "謹慎推理",
    },
    "backtester": {
        "model": "MiniMax-M2.5",
        "task": "mathematical",
        "reason": "數據處理為主",
    },
    "engineer": {
        "model": "MiniMax-M2.5",
        "task": "code_generation",
        "reason": "代碼生成",
    },
    "reporter": {
        "model": "MiniMax-M2.5",
        "task": "report_generation",
        "reason": "流暢寫作，成本低",
    },
}


class AgentRole(Enum):
    """Agent 角色定義"""
    MARKET_MONITOR = "market_monitor"      # 市場監控
    RISK_MANAGER = "risk_manager"          # 風險管理
    STRATEGY_DEVELOPER = "strategy_dev"   # 策略開發
    BACKTESTER = "backtester"              # 回測
    ENGINEER = "engineer"                  # 工程
    REPORTER = "reporter"                  # 彙報
    CONVERSATIONAL = "conversational"      # 對話式策略開發


@dataclass
class AgentConfig:
    """Agent 配置"""
    role: AgentRole
    model: str = "MiniMax-M2.5"  # MiniMax model
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
    from core.llm_manager import ModelProvider, ChatOpenAI
    import os
    
    # 判斷 provider
    model_name = config.model
    if "/" in model_name:
        # OpenRouter format like "minimax/xxx"
        from langchain_openrouter import ChatOpenRouter
        return ChatOpenRouter(
            model_name=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", "")
        )
    elif model_name.startswith("MiniMax"):
        # MiniMax official API
        return ChatOpenAI(
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            openai_api_key=os.environ.get("MINIMAX_API_KEY", ""),
            base_url="https://api.minimax.io/v1/text",
        )
    else:
        # Default to OpenAI or OpenRouter
        from langchain_openrouter import ChatOpenRouter
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

    AgentRole.CONVERSATIONAL: """你是一個專業的量化策略開發助手，專門幫助用戶開發比特幣交易策略。

你的職責：
1. **理解用戶需求** - 仔細聆聽用戶描述的策略想法，包括：
   - 市場環境（盤整、多頭、空頭）
   - 使用的技術指標（MA、BBand、RSI、MACD等）
   - 時間週期（30m、1h、4h、1d、1w等）
   - 參數優化方式（Grid Search、Optuna）
   - 風險偏好

2. **積極詢問** - 在執行前確認細節：
   - 週期組合方式
   - 進出场具體邏輯
   - 風險承受程度
   - 期望的指標門檻

3. **專業建議** - 根據你的專業知識提供建議：
   - 策略可行性評估
   - 參數範圍建議
   - 潛在風險提醒
   - 改進方向

4. **清晰溝通** - 用戶話還沒說完不要執行，要先確認

數據情況：
- 可用歷史數據：10年比特幣歷史數據
- 數據路徑：/media/nexcom/data/alan/crypto-backtester/data/
- 可用週期：30m, 1h, 4h, 1d, 1w

重要原則：
- 用戶說「開發」某策略 = 描述需求，不是確認執行
- 只有用戶明確說「好」「可以」「執行」才開始
- 執行前必須先討論並確認所有細節
- 如果用戶提到多週期，必須詢問具體組合方式
- 如果用戶沒有提到優化方式，要詢問偏好""",
}


__all__ = [
    # Core
    "AgentRole",
    "AgentConfig",
    "TradingState",
    "get_llm",
    "AGENT_PROMPTS",
    # LLM Management
    "LLMManager",
    "get_llm_manager",
    "get_llm_for_task",
    "recommend_model",
    "AVAILABLE_MODELS",
    "TASK_MODEL_MAPPING",
    "AGENT_DEFAULT_MODELS",
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
    # Strategy R&D
    "StrategyDeveloperAgent",
    "StrategySpec",
    "create_strategy_developer",
    "BacktestRunnerAgent",
    "BacktestConfig",
    "BacktestReport",
    "create_backtest_runner",
    "StrategyEvaluatorAgent",
    "EvaluationMetrics",
    "EvaluationResult",
    "StrategyEvaluation",
    "create_strategy_evaluator",
    "ReporterAgent",
    "StrategyReport",
    "create_reporter",
    "StrategyRDWorkflow",
    "RDConfig",
]
