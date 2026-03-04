"""
多智能體交易系統 - 使用範例

這個範例展示如何使用 LangGraph + OpenRouter 建立多智能體交易系統。

使用前請設置環境變數：
export OPENROUTER_API_KEY="你的_api_key"
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents import AgentRole, AgentConfig, get_llm, AGENT_PROMPTS
from agents.workflow import create_trading_workflow, run_trading_workflow


def example_single_agent():
    """範例：使用單一 Agent 進行市場分析"""
    print("=" * 60)
    print("範例 1: 單一 Agent 市場分析")
    print("=" * 60)
    
    # 檢查 API Key
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("⚠️  請設置 OPENROUTER_API_KEY 環境變數")
        print("   export OPENROUTER_API_KEY='your_api_key'")
        return
    
    # 配置 Agent
    config = AgentConfig(
        role=AgentRole.MARKET_MONITOR,
        model="openai/gpt-4o-mini",
        temperature=0.7
    )
    
    # 建立 LLM
    llm = get_llm(config)
    
    # 測試請求
    test_data = """
    BTC/USDT:
    - 價格: 67500 USDT
    - 24h 變化: +2.5%
    - 成交量: 28.5B USDT
    - 訂單簿: 買單深度充足
    """
    
    prompt = f"請分析以下市場數據：\n{test_data}"
    
    print("\n📊 市場數據:")
    print(test_data)
    print("\n🤖 Agent 分析結果:")
    
    response = llm.invoke(prompt)
    print(response.content)


def example_workflow():
    """範例：運行完整工作流"""
    print("\n" + "=" * 60)
    print("範例 2: 完整交易決策工作流")
    print("=" * 60)
    
    # 模擬市場數據
    market_data = {
        "symbol": "BTC/USDT",
        "price": 67500,
        "change_24h": 2.5,
        "volume_24h": 28500000000,
        "order_book": {"bid_depth": 1500000, "ask_depth": 1200000},
        "rsi": 65,
        "macd": {"histogram": 150, "signal": "bullish"}
    }
    
    print(f"\n📊 輸入市場數據: {market_data}")
    
    # 檢查 API Key
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("⚠️  請設置 OPENROUTER_API_KEY 環境變數")
        return
    
    # 運行工作流
    print("\n🚀 運行多智能體工作流...")
    print("   (這會依次調用: Market Monitor → Risk Manager → Strategy Dev → Backtester → Reporter)")
    
    try:
        result = run_trading_workflow(market_data)
        
        print("\n✅ 工作流完成!")
        print("\n📝 最終報告:")
        print("-" * 40)
        print(result.get("final_report", "無報告"))
        
    except Exception as e:
        print(f"\n❌ 錯誤: {e}")
        print("   請確認 OPENROUTER_API_KEY 正確設定")


def show_architecture():
    """顯示系統架構"""
    print("\n" + "=" * 60)
    print("系統架構說明")
    print("=" * 60)
    
    print("""
┌─────────────────────────────────────────────────────────────┐
│                     交易決策工作流                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌───────────────┐                                         │
│  │ Market Monitor │ ◄── 市場監控 (價格、趨勢、異常)           │
│  └───────┬───────┘                                         │
│          │                                                 │
│          ▼                                                 │
│  ┌───────────────┐                                         │
│  │  Risk Manager │ ◄── 風險評估 (倉位、風險等級)              │
│  └───────┬───────┘                                         │
│          │                                                 │
│          ▼                                                 │
│  ┌───────────────┐                                         │
│  │Strategy Developer│ ◄── 策略開發 (信號、參數)              │
│  └───────┬───────┘                                         │
│          │                                                 │
│          ▼                                                 │
│  ┌───────────────┐                                         │
│  │   Backtester  │ ◄── 回測驗證 (歷史表現)                   │
│  └───────┬───────┘                                         │
│          │                                                 │
│          ▼                                                 │
│  ┌───────────────┐                                         │
│  │    Reporter   │ ◄── 彙總報告 (人類可讀)                   │
│  └───────────────┘                                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘

每個 Agent 可以:
- 訪問共享狀態 (TradingState)
- 讀取前一個 Agent 的輸出
- 決定下一個執行的 Agent
- 輸出結構化決策
""")


def main():
    """主函數"""
    print("""
╔════════════════════════════════════════════════════════════╗
║         Crypto Backtester - 多智能體系統範例                ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    # 顯示架構
    show_architecture()
    
    # 單一 Agent 範例
    example_single_agent()
    
    # 完整工作流範例
    example_workflow()
    
    print("\n" + "=" * 60)
    print("範例完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
