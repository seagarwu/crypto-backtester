"""多智能體 Workflow - 使用 LangGraph StateGraph"""

from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.prebuilt import ToolNode

from . import AgentRole, AgentConfig, TradingState, get_llm, AGENT_PROMPTS


# 定義 Graph 狀態
class AgentState(TypedDict):
    """多智能體系統的共享狀態"""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    market_data: dict
    risk_assessment: dict
    strategy_proposal: dict
    backtest_result: dict
    code_output: str
    final_report: str
    next_agent: str


def create_market_monitor_node():
    """創建市場監控 Agent 節點"""
    def market_monitor_node(state: AgentState) -> AgentState:
        config = AgentConfig(
            role=AgentRole.MARKET_MONITOR,
            system_prompt=AGENT_PROMPTS[AgentRole.MARKET_MONITOR]
        )
        llm = get_llm(config)
        
        # 模擬市場數據（實際應該從 API 獲取）
        market_info = state.get("market_data", {})
        
        prompt = f"""分析以下市場數據：
{market_info}

請提供你的市場分析。"""
        
        response = llm.invoke(prompt)
        
        return {
            "messages": [response],
            "next_agent": "risk_manager"
        }
    
    return market_monitor_node


def create_risk_manager_node():
    """創建風險管理 Agent 節點"""
    def risk_manager_node(state: AgentState) -> AgentState:
        config = AgentConfig(
            role=AgentRole.RISK_MANAGER,
            system_prompt=AGENT_PROMPTS[AgentRole.RISK_MANAGER]
        )
        llm = get_llm(config)
        
        # 獲取市場監控結果
        messages = state.get("messages", [])
        market_report = messages[-1].content if messages else "無市場數據"
        
        prompt = f"""根據市場監控報告：
{market_report}

請進行風險評估並給出交易建議。"""
        
        response = llm.invoke(prompt)
        
        return {
            "messages": [response],
            "risk_assessment": {"report": response.content, "approved": True},
            "next_agent": "strategy_developer"
        }
    
    return risk_manager_node


def create_strategy_developer_node():
    """創建策略開發 Agent 節點"""
    def strategy_developer_node(state: AgentState) -> AgentState:
        config = AgentConfig(
            role=AgentRole.STRATEGY_DEVELOPER,
            system_prompt=AGENT_PROMPTS[AgentRole.STRATEGY_DEVELOPER]
        )
        llm = get_llm(config)
        
        messages = state.get("messages", [])
        context = "\n".join([m.content for m in messages[-2:]]) if len(messages) >= 2 else "無上下文"
        
        prompt = f"""根據以下分析：
{context}

請提出策略建議。"""
        
        response = llm.invoke(prompt)
        
        return {
            "messages": [response],
            "strategy_proposal": {"strategy": response.content, "params": {}},
            "next_agent": "backtester"
        }
    
    return strategy_developer_node


def create_backtester_node():
    """創建回測 Agent 節點"""
    def backtester_node(state: AgentState) -> AgentState:
        config = AgentConfig(
            role=AgentRole.BACKTESTER,
            system_prompt=AGENT_PROMPTS[AgentRole.BACKTESTER]
        )
        llm = get_llm(config)
        
        strategy = state.get("strategy_proposal", {}).get("strategy", "無策略")
        
        prompt = f"""對以下策略進行回測評估：
{strategy}

請提供回測結果（可以使用模擬數據）。"""
        
        response = llm.invoke(prompt)
        
        return {
            "messages": [response],
            "backtest_result": {"result": response.content, "passed": True},
            "next_agent": "reporter"
        }
    
    return backtester_node


def create_reporter_node():
    """創建彙報 Agent 節點"""
    def reporter_node(state: AgentState) -> AgentState:
        config = AgentConfig(
            role=AgentRole.REPORTER,
            system_prompt=AGENT_PROMPTS[AgentRole.REPORTER]
        )
        llm = get_llm(config)
        
        messages = state.get("messages", [])
        all_analysis = "\n".join([m.content for m in messages])
        
        prompt = f"""根據以下所有分析，生成最終報告：
{all_analysis}

請生成簡潔的執行摘要。"""
        
        response = llm.invoke(prompt)
        
        return {
            "messages": [response],
            "final_report": response.content
        }
    
    return reporter_node


def should_continue(state: AgentState) -> str:
    """決定是否繼續流程"""
    next_agent = state.get("next_agent", "")
    if next_agent == "reporter":
        return "reporter"
    return next_agent


def create_trading_workflow() -> StateGraph:
    """創建完整的交易決策工作流"""
    
    # 創建圖
    workflow = StateGraph(AgentState)
    
    # 添加節點
    workflow.add_node("market_monitor", create_market_monitor_node())
    workflow.add_node("risk_manager", create_risk_manager_node())
    workflow.add_node("strategy_developer", create_strategy_developer_node())
    workflow.add_node("backtester", create_backtester_node())
    workflow.add_node("reporter", create_reporter_node())
    
    # 設置入口點
    workflow.set_entry_point("market_monitor")
    
    # 添加條件邊
    workflow.add_conditional_edges(
        "market_monitor",
        should_continue,
        {
            "risk_manager": "risk_manager"
        }
    )
    
    workflow.add_conditional_edges(
        "risk_manager",
        should_continue,
        {
            "strategy_developer": "strategy_developer"
        }
    )
    
    workflow.add_conditional_edges(
        "strategy_developer",
        should_continue,
        {
            "backtester": "backtester"
        }
    )
    
    workflow.add_conditional_edges(
        "backtester",
        should_continue,
        {
            "reporter": "reporter"
        }
    )
    
    # 設置結束點
    workflow.add_edge("reporter", END)
    
    return workflow


def run_trading_workflow(market_data: dict) -> dict:
    """運行交易決策工作流"""
    workflow = create_trading_workflow()
    app = workflow.compile()
    
    # 初始化狀態
    initial_state = {
        "messages": [],
        "market_data": market_data,
        "risk_assessment": {},
        "strategy_proposal": {},
        "backtest_result": {},
        "code_output": "",
        "final_report": "",
        "next_agent": ""
    }
    
    # 運行
    result = app.invoke(initial_state)
    
    return result


# 便捷函數：快速運行單一類型分析
async def analyze_market(market_data: dict, api_key: str) -> str:
    """快速市場分析"""
    import os
    os.environ["OPENROUTER_API_KEY"] = api_key
    
    config = AgentConfig(
        role=AgentRole.MARKET_MONITOR,
        system_prompt=AGENT_PROMPTS[AgentRole.MARKET_MONITOR]
    )
    llm = get_llm(config)
    
    response = llm.invoke(f"分析以下市場數據：{market_data}")
    return response.content
