"""
多智能體交易系統 - 使用範例

這個範例展示如何使用獨立 Agent 進行交易決策。

使用前請設置環境變數：
export OPENROUTER_API_KEY="你的_api_key"
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents import AgentRole
from agents.workflow import create_agent, run_single_agent


def example_market_monitor():
    """範例：市場監控 Agent"""
    print("=" * 60)
    print("範例 1: Market Monitor Agent")
    print("=" * 60)
    
    # 檢查 API Key
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("⚠️  請設置 OPENROUTER_API_KEY 環境變數")
        return
    
    # 建立 Agent
    agent = create_agent(AgentRole.MARKET_MONITOR)
    
    # 測試數據
    market_data = {
        "symbol": "BTC/USDT",
        "price": 67500,
        "change_24h": "+2.5%",
        "volume_24h": "28.5B USDT",
        "rsi": 65,
        "macd": "bullish"
    }
    
    print(f"\n📊 市場數據: {market_data}")
    print("\n🤖 Agent 分析結果:")
    
    result = agent.analyze_market(market_data)
    print(result)


def example_risk_manager():
    """範例：風險管理 Agent"""
    print("\n" + "=" * 60)
    print("範例 2: Risk Manager Agent")
    print("=" * 60)
    
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("⚠️  請設置 OPENROUTER_API_KEY 環境變數")
        return
    
    agent = create_agent(AgentRole.RISK_MANAGER)
    
    portfolio = {
        "total_value": 10000,
        "position_size": 0.3,
        "risk_level": "medium"
    }
    market_state = "多頭市場，RSI 65"
    
    print(f"\n📊 投資組合: {portfolio}")
    print(f"📊 市場狀態: {market_state}")
    
    result = agent.assess_risk(portfolio, market_state)
    print("\n🤖 風險評估結果:")
    print(result)


def example_strategy_developer():
    """範例：策略開發 Agent"""
    print("\n" + "=" * 60)
    print("範例 3: Strategy Developer Agent")
    print("=" * 60)
    
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("⚠️  請設置 OPENROUTER_API_KEY 環境變數")
        return
    
    agent = create_agent(AgentRole.STRATEGY_DEVELOPER)
    
    market_state = "上升趨勢，MACD 金叉"
    strategies = ["MA Cross", "RSI Reversal"]
    
    result = agent.develop_strategy(market_state, strategies)
    print("\n🤖 策略建議:")
    print(result)


def example_quick_call():
    """範例：快速調用"""
    print("\n" + "=" * 60)
    print("範例 4: 快速調用 (run_single_agent)")
    print("=" * 60)
    
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("⚠️  請設置 OPENROUTER_API_KEY 環境變數")
        return
    
    # 一行命令調用
    result = run_single_agent(
        AgentRole.BACKTESTER,
        "測試 MA Cross 策略，回測期間一個月"
    )
    print("\n🤖 回測結果:")
    print(result)


def show_available_agents():
    """顯示可用的 Agents"""
    print("\n" + "=" * 60)
    print("可用的獨立 Agents")
    print("=" * 60)
    
    for role in AgentRole:
        print(f"  • {role.name}: {role.value}")


def main():
    """主函數"""
    print("""
╔════════════════════════════════════════════════════════════╗
║     Crypto Backtester - 獨立 Agent 系統範例                 ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    show_available_agents()
    
    # 範例
    example_market_monitor()
    example_risk_manager()
    example_strategy_developer()
    example_quick_call()
    
    print("\n" + "=" * 60)
    print("範例完成")
    print("=" * 60)
    print("""
💡 每個 Agent 都可以獨立運行！
   後續可透過 YAML 配置調整工作流。
""")


if __name__ == "__main__":
    main()
