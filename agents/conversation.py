#!/usr/bin/env python3
"""
Conversational Strategy Developer - 對話式策略開發助手

用自然語言與用戶互動，幫助開發交易策略。

使用方式:
    python -m agents.conversation
"""

import os
import sys
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

# 確保可以匯入模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.strategy_developer_agent import StrategyDeveloperAgent, StrategySpec
from agents.backtest_runner_agent import (
    BacktestRunnerAgent, 
    BacktestConfig, 
    BacktestReport,
    create_backtest_runner,
)
from agents.strategy_evaluator_agent import (
    StrategyEvaluatorAgent,
    EvaluationMetrics,
    EvaluationResult,
    create_strategy_evaluator,
)
from agents.reporter_agent import ReporterAgent
from reports import generate_backtest_report

logger = logging.getLogger(__name__)


class ConversationalStrategyDeveloper:
    """對話式策略開發助手"""
    
    def __init__(self):
        self.developer = StrategyDeveloperAgent()
        self.evaluator = create_strategy_evaluator()
        self.runner = create_backtest_runner()
        self.reporter = ReporterAgent()
        
        # 對話歷史
        self.conversation_history: List[Dict[str, str]] = []
        self.current_strategy: Optional[StrategySpec] = None
        self.current_result: Optional["BacktestReport"] = None
    
    def add_message(self, role: str, content: str):
        """添加對話記錄"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
    
    def print_welcome(self):
        """打印歡迎訊息"""
        print("""
╔══════════════════════════════════════════════════════════════╗
║         🤖 對話式策略開發助手                                ║
╠══════════════════════════════════════════════════════════════╣
║  我可以幫你：                                                 ║
║  • 根據你的想法開發交易策略                                   ║
║  • 自動回測並評估表現                                         ║
║  • 優化策略參數                                              ║
║  • 產出完整的策略報告                                         ║
║                                                               ║
║  輸入範例：                                                   ║
║  • "我想做比特幣一小時的短線策略"                            ║
║  • "幫我開發一個均線交叉策略"                                ║
║  • "我想要做突破策略，配合成交量過濾"                        ║
║                                                               ║
║  命令：                                                       ║
║  • quit - 退出                                               ║
║  • help - 顯示幫助                                           ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    def parse_user_intent(self, message: str) -> Dict[str, Any]:
        """解析用戶意圖"""
        message = message.lower()
        
        intent = {
            "type": "develop",
            "symbol": "BTCUSDT",
            "interval": "1h",
            "strategy_type": None,
            "indicators": [],
            "requirements": [],
        }
        
        # 解析交易對
        if "btc" in message:
            intent["symbol"] = "BTCUSDT"
        elif "eth" in message:
            intent["symbol"] = "ETHUSDT"
        
        # 解析時間框架
        if "15分" in message or "15m" in message:
            intent["interval"] = "15m"
        elif "30分" in message or "30m" in message:
            intent["interval"] = "30m"
        elif "4小時" in message or "4h" in message:
            intent["interval"] = "4h"
        elif "日線" in message or "1d" in message:
            intent["interval"] = "1d"
        elif "小時" in message or "1h" in message:
            intent["interval"] = "1h"
        
        # 解析策略類型
        if "均線" in message or "ma" in message or "交叉" in message:
            intent["strategy_type"] = "ma_crossover"
            intent["indicators"].append("MA")
        if "rsi" in message:
            intent["strategy_type"] = "rsi"
            intent["indicators"].append("RSI")
        if "macd" in message:
            intent["strategy_type"] = "macd"
            intent["indicators"].append("MACD")
        if "bb" in message or "布林" in message:
            intent["strategy_type"] = "bollinger"
            intent["indicators"].append("BBand")
        if "突破" in message:
            intent["strategy_type"] = "breakout"
            intent["indicators"].append("Breakout")
        if "成交量" in message or "量" in message:
            intent["requirements"].append("volume_filter")
        
        # 解析風格
        if "短線" in message or "日內" in message:
            intent["style"] = "scalping"
        elif "波段" in message or "中線" in message:
            intent["style"] = "swing"
        elif "長線" in message or "趨勢" in message:
            intent["style"] = "trend_following"
        
        return intent
    
    def develop_strategy_from_intent(self, intent: Dict, market_context: str = "") -> StrategySpec:
        """根據意圖開發策略"""
        strategy_type = intent.get("strategy_type", "ma_crossover") or "ma_crossover"
        
        # 構建策略描述
        desc_parts = []
        if intent.get("style"):
            style_map = {
                "scalping": "短線日內交易",
                "swing": "波段交易",
                "trend_following": "趨勢跟隨"
            }
            desc_parts.append(style_map[intent["style"]])
        
        if intent.get("indicators"):
            desc_parts.append(" + ".join(intent["indicators"]))
        
        description = f"{intent['symbol']} {intent['interval']} " + " ".join(desc_parts)
        
        # 根據策略類型生成規格
        if strategy_type == "ma_crossover":
            spec = StrategySpec(
                name=f"{intent['symbol']} MA策略",
                description=description,
                indicators=["MA5", "MA20", "MA60"],
                parameters={
                    "short_window": 20,
                    "long_window": 60,
                },
                risk_level="medium",
                timeframe=intent["interval"],
            )
        elif strategy_type == "rsi":
            spec = StrategySpec(
                name=f"{intent['symbol']} RSI策略",
                description=description,
                indicators=["RSI"],
                parameters={
                    "rsi_period": 14,
                    "oversold": 30,
                    "overbought": 70,
                },
                risk_level="medium",
                timeframe=intent["interval"],
            )
        elif strategy_type == "breakout":
            spec = StrategySpec(
                name=f"{intent['symbol']} 突破策略",
                description=description,
                indicators=["High", "Volume"],
                parameters={
                    "lookback_period": 20,
                    "volume_multiplier": 1.5,
                },
                risk_level="high",
                timeframe=intent["interval"],
            )
        else:
            # 默認 MA 策略
            spec = StrategySpec(
                name=f"{intent['symbol']} 策略",
                description=description,
                indicators=["MA20", "MA50"],
                parameters={
                    "short_window": 20,
                    "long_window": 50,
                },
                risk_level="medium",
                timeframe=intent["interval"],
            )
        
        return spec
    
    def clarify_requirements(self, intent: Dict) -> str:
        """詢問用戶以澄清需求"""
        questions = []
        
        if not intent.get("strategy_type"):
            questions.append("""
你想要什麼類型的策略？
  A) 均線交叉 - 快速均線上穿慢速均線時買入
  B) RSI 超買超賣 - RSI 低於 30 買入，高於 70 賣出
  C) 突破策略 - 價格突破近期高點時買入
  D) 布林帶 - 價格觸及布林帶下軌買入，上軌賣出
  E) 描述你自己的想法
""")
        
        if not intent.get("style"):
            questions.append("""
你想做什麼風格的交易？
  1) 短線 - 幾分鐘到幾小時持倉
  2) 波段 - 几天到几周持倉
  3) 長線 - 幾個月持倉
""")
        
        return "\n".join(questions)
    
    def run_interactive(self):
        """運行對話式開發"""
        self.print_welcome()
        
        # 初始問候
        print("\n👋 你好！請告訴我你想開發什麼樣的策略。")
        print("   例如：\"我想做比特幣一小時的短線策略\"")
        
        while True:
            try:
                print("\n" + "─" * 50)
                user_input = input("\n💬 你: ").strip()
                
                if not user_input:
                    continue
                
                # 命令處理
                if user_input.lower() in ["quit", "exit", "退出"]:
                    print("\n👋 再見！")
                    break
                
                if user_input.lower() in ["help", "幫助", "?"]:
                    self.print_welcome()
                    continue
                
                self.add_message("user", user_input)
                
                # 解析意圖
                intent = self.parse_user_intent(user_input)
                
                # 如果意圖不明確，詢問用戶
                if not intent.get("strategy_type"):
                    question = self.clarify_requirements(intent)
                    print(f"\n🤖 {question}")
                    self.add_message("assistant", question)
                    continue
                
                # 確認理解
                symbol = intent["symbol"]
                interval = intent["interval"]
                style = intent.get("style", "未知")
                
                print(f"""
🤖 我理解了！你想要：
   • 交易對: {symbol}
   • 時間框架: {interval}
   • 策略類型: {intent.get('strategy_type')}
   • 交易風格: {style}

   正在開發策略...
""")
                
                # 開發策略
                spec = self.develop_strategy_from_intent(intent, user_input)
                self.current_strategy = spec
                
                print(f"   📝 策略: {spec.name}")
                print(f"   📊 指標: {', '.join(spec.indicators)}")
                print(f"   ⚙️  參數: {spec.parameters}")
                
                # 詢問是否繼續
                print("""
   是否繼續？
   y) 確認，開始回測
   n) 重新描述
""")
                
                confirm = input("   > ").strip().lower()
                
                if confirm != "y":
                    print("\n好的，請重新描述你的策略想法。")
                    continue
                
                # 執行回測
                print("\n   🔄 執行回測...")
                
                try:
                    # 嘗試載入數據
                    from data import load_csv
                    
                    data_path = f"data/{intent['symbol']}_{intent['interval']}.csv"
                    
                    # 嘗試不同路徑
                    for path in [data_path, f"../{data_path}", f"./{data_path}"]:
                        if os.path.exists(path):
                            data_path = path
                            break
                    
                    if not os.path.exists(data_path):
                        print(f"""
   ⚠️  找不到數據文件: {data_path}
   
   請先下載數據：
   python scripts/run_trading_system.py --download --symbols {intent['symbol']} --interval {intent['interval']} --years 1
""")
                        continue
                    
                    print(f"   📂 使用數據: {data_path}")
                    
                    # 執行回測 - 使用 BacktestConfig
                    config = BacktestConfig(
                        symbol=intent["symbol"],
                        interval=intent["interval"],
                    )
                    
                    backtest_report = self.runner.run_backtest(
                        strategy_name="ma_crossover",
                        strategy_params=spec.parameters,
                        config=config,
                    )
                    self.current_result = backtest_report
                    
                    # 評估
                    print("   📈 評估策略...")
                    evaluation = self.evaluator.evaluate(backtest_report)
                    
                    # 顯示結果
                    print(f"""
╔══════════════════════════════════════════════════════════╗
║                    📊 回測結果                           ║
╠══════════════════════════════════════════════════════════╣
║  Sharpe Ratio:  {backtest_report.sharpe_ratio:.2f}                        ║
║  Max Drawdown:  {backtest_report.max_drawdown:.1f}%                        ║
║  Win Rate:      {backtest_report.win_rate:.1f}%                        ║
║  Total Trades:  {backtest_report.total_trades}                          ║
║  Profit Factor: {backtest_report.profit_factor:.2f}                        ║
╠══════════════════════════════════════════════════════════╣
║  評估結果: {evaluation.result.name:<45}║
╚══════════════════════════════════════════════════════════╝
""")
                    
                    # 詢問是否保存報告
                    print("""
   是否保存報告？
   y) 是，生成完整報告
   n) 否
""")
                    
                    save_report = input("   > ").strip().lower()
                    
                    if save_report == "y":
                        # 生成報告
                        from data import load_csv
                        price_df = load_csv(data_path)
                        
                        output = generate_backtest_report(
                            result=backtest_report,
                            price_df=price_df,
                            title=spec.name,
                        )
                        
                        print(f"""
   ✅ 報告已生成！
   📁 文件位置:
      • HTML報告: {output.get('html_report', 'N/A')}
      • 買賣點圖: {output.get('trades', 'N/A')}
      • 資產曲線: {output.get('equity_curve', 'N/A')}
      • 回撤圖: {output.get('drawdown', 'N/A')}
""")
                    
                    # 詢問是否繼續
                    print("""
   是否繼續開發其他策略？
   y) 是
   n) 否
""")
                    
                    continue_dev = input("   > ").strip().lower()
                    
                    if continue_dev != "y":
                        print("\n👋 謝謝使用，再見！")
                        break
                
                except Exception as e:
                    print(f"\n   ❌ 執行出错: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
                    
            except KeyboardInterrupt:
                print("\n\n👋 中斷對話，再見！")
                break
            except EOFError:
                break


def main():
    """主入口"""
    developer = ConversationalStrategyDeveloper()
    developer.run_interactive()


if __name__ == "__main__":
    main()
