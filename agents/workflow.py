"""多智能體 Workflow - 獨立 Agent 執行"""

from typing import TypedDict, Annotated, Sequence, Callable, Optional, List, Dict, Any
import operator
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from . import AgentRole, AgentConfig, TradingState, get_llm, AGENT_PROMPTS


# ==================== 獨立 Agent 執行器 ====================

class AgentExecutor:
    """獨立 Agent 執行器 - 每個 Agent 可單獨運行"""
    
    def __init__(self, role: AgentRole, model: str = "minimax/minimax-chat"):
        self.role = role
        self.config = AgentConfig(
            role=role,
            model=model,
            system_prompt=AGENT_PROMPTS[role]
        )
        self.llm = None
    
    def _get_llm(self):
        """懒加载 LLM"""
        if self.llm is None:
            self.llm = get_llm(self.config)
        return self.llm
    
    def run(self, prompt: str) -> str:
        """執行 Agent - 輸入 prompt，返回回應"""
        llm = self._get_llm()
        response = llm.invoke(prompt)
        return response.content
    
    def analyze_market(self, market_data: Dict[str, Any]) -> str:
        """市場監控專用"""
        data_str = "\n".join([f"- {k}: {v}" for k, v in market_data.items()])
        prompt = f"請分析以下市場數據：\n{data_str}"
        return self.run(prompt)
    
    def assess_risk(self, portfolio: Dict[str, Any], market_state: str) -> str:
        """風險管理專用"""
        portfolio_str = "\n".join([f"- {k}: {v}" for k, v in portfolio.items()])
        prompt = f"""投資組合狀態：
{portfolio_str}

市場狀態：{market_state}

請進行風險評估並給出交易建議。"""
        return self.run(prompt)
    
    def develop_strategy(self, market_state: str, existing_strategies: List[str] = None) -> str:
        """策略開發專用"""
        strategies = existing_strategies or ["無"]
        prompt = f"""市場環境：{market_state}

現有策略：{', '.join(strategies)}

請提出策略建議。"""
        return self.run(prompt)
    
    def backtest(self, strategy: str, timeframe: str = "過去30天") -> str:
        """回測專用"""
        prompt = f"""對以下策略進行回測：
{strategy}

回測期間：{timeframe}

請提供回測結果。"""
        return self.run(prompt)
    
    def write_code(self, requirement: str) -> str:
        """工程師專用"""
        prompt = f"""需求：{requirement}

請提供代碼實現。"""
        return self.run(prompt)
    
    def generate_report(self, agent_results: Dict[str, str]) -> str:
        """彙報專用"""
        results_str = "\n".join([f"## {agent}\n{result}" for agent, result in agent_results.items()])
        prompt = f"""根據以下分析結果，生成最終報告：

{results_str}

請生成執行摘要。"""
        return self.run(prompt)


# ==================== 便捷函數 ====================

def create_agent(role: AgentRole, model: str = "minimax/minimax-chat") -> AgentExecutor:
    """建立獨立 Agent"""
    return AgentExecutor(role, model)


def run_single_agent(role: AgentRole, prompt: str, model: str = "minimax/minimax-chat") -> str:
    """快速運行單一 Agent"""
    agent = create_agent(role, model)
    return agent.run(prompt)
