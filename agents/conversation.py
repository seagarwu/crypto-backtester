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
from pathlib import Path
import logging
import pandas as pd

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
    
    def analyze_strategy_requirements(self, message: str) -> Dict[str, Any]:
        """分析用戶的策略需求，生成確認問題"""
        intent = self.parse_user_intent(message)
        
        # 識別複雜需求
        analysis = {
            "has_multi_timeframe": any(t in message for t in ["30m", "1h", "4h", "1d", "1w", "多週期", "多周期"]),
            "needs_optimization": any(w in message for w in ["優化", "優化", "grid", "optuna", "參數"]),
            "market_condition": None,
            "indicators_mentioned": [],
            "clarification_questions": [],
        }
        
        # 識別市場條件
        if "盤整" in message or "區間" in message:
            analysis["market_condition"] = "range"
        elif "多頭" in message or "上漲" in message:
            analysis["market_condition"] = "bull"
        elif "空頭" in message or "下跌" in message:
            analysis["market_condition"] = "bear"
        
        # 識別提到的指標
        if "ma" in message.lower() or "均線" in message:
            analysis["indicators_mentioned"].append("MA")
        if "bb" in message.lower() or "布林" in message:
            analysis["indicators_mentioned"].append("BBand")
        if "rsi" in message:
            analysis["indicators_mentioned"].append("RSI")
        if "macd" in message:
            analysis["indicators_mentioned"].append("MACD")
        if "量" in message or "volume" in message.lower():
            analysis["indicators_mentioned"].append("Volume")
        
        # 生成確認問題
        questions = []
        
        if analysis["has_multi_timeframe"]:
            questions.append("1. 你說的多週期策略，具體要用哪些週期？例如 30m 當主要週期，1h/4h 當確認？")
        
        if analysis["needs_optimization"]:
            questions.append("2. 參數優化方面，你傾向用 Grid Search (網格搜索) 還是 Optuna (貝葉斯優化)？")
        
        if analysis["market_condition"] == "range":
            questions.append("3. 盤整盤策略通常用 BBand 來抓區間，你希望價格碰到下軌買入、上軌賣出？還是有其他想法？")
        
        if analysis["indicators_mentioned"]:
            indicators_str = "、".join(analysis["indicators_mentioned"])
            questions.append(f"4. 你提到的指標是 {indicators_str}，有特定的參數偏好嗎？")
        
        # 通用問題
        if not questions:
            questions.append("1. 請問你希望這個策略的風格是短線、波段還是長線？")
        
        questions.append("2. 你的風險承受程度是高、中、還是低？")
        
        analysis["clarification_questions"] = questions
        
        # 初步策略建議
        if analysis["market_condition"] == "range" and "BBand" in analysis["indicators_mentioned"]:
            analysis["preliminary_idea"] = """
📋 根據你的需求，我初步的想法是：

【策略方向】
- 市場環境：比特幣處於盤整/區間震盪
- 核心指標：布林帶 (BBand) + 移動平均線 (MA)
- 多週期確認：使用 30m 為交易週期，1h/4h 確認趨勢

【具體做法】
- 價格觸及 BBand 下軌時買入，上軌時賣出
- 用 MA 過濾假突破（例如價格在 MA 之上才做多）
- 多週期共振：30m 出現訊號時，確認 1h/4h 趨勢方向一致

【參數優化】
- BBand: period (10-30), std (1.5-2.5)
- MA: 週期組合測試 (如 20/50, 30/60, 50/200)
- 這部分可以用 Optuna 自動優化
"""
        
        return analysis
    
    def discuss_strategy(self, message: str) -> str:
        """討論策略，不直接執行"""
        analysis = self.analyze_strategy_requirements(message)
        
        response = "\n" + "=" * 60
        response += "\n🔍 我理解你的需求了！"
        response += "\n" + "=" * 60
        
        response += f"""
📌 辨識到的關鍵點：
   • 多週期分析: {'是' if analysis['has_multi_timeframe'] else '否'}
   • 需要參數優化: {'是' if analysis['needs_optimization'] else '否'}
   • 市場環境: {analysis['market_condition'] or '未指定'}
   • 提到的指標: {', '.join(analysis['indicators_mentioned']) or '無'}
"""
        
        if analysis.get("preliminary_idea"):
            response += analysis["preliminary_idea"]
        
        response += "\n" + "-" * 60
        response += "\n❓ 在開始開發之前，請確認以下問題：\n"
        
        for q in analysis["clarification_questions"]:
            response += f"\n{q}"
        
        response += """
\n-" * 60
請回复你的答案，或者直接說「可以，開始開發」，我就會著手進行！
"""
        
        return response
    
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
                
                # 檢查是否確認開始開發
                if any(kw in user_input.lower() for kw in ["開始", "開發", "確認", "ok", "yes", "好", "可以"]):
                    # 用戶確認，開始執行
                    if self.current_strategy is None:
                        # 沒有策略，需要先分析
                        intent = self.parse_user_intent(user_input)
                        if not intent.get("strategy_type"):
                            question = self.clarify_requirements(intent)
                            print(f"\n🤖 {question}")
                            continue
                        spec = self.develop_strategy_from_intent(intent, user_input)
                    else:
                        spec = self.current_strategy
                    
                    # 執行開發流程
                    self._execute_development(spec, user_input)
                    continue
                
                # 先討論策略，不直接執行
                discussion = self.discuss_strategy(user_input)
                print(f"\n🤖 {discussion}")
                self.add_message("assistant", discussion)
                
            except KeyboardInterrupt:
                print("\n\n👋 中斷對話，再見！")
                break
            except EOFError:
                break

    def _execute_development(self, spec, user_input: str = ""):
        """執行策略開發流程"""
        try:
            intent = self.parse_user_intent(user_input)
            interval = intent.get("interval", "1h")
            symbol = intent.get("symbol", "BTCUSDT")
            
            # 嘗試載入數據
            project_root = Path(__file__).parent.parent
            data_path = str(project_root / "data" / f"{symbol}_{interval}.csv")
            
            if not os.path.exists(data_path):
                # 嘗試新月格式
                interval_dir = project_root / "data" / interval
                if interval_dir.exists():
                    files = sorted((interval_dir / f"{symbol}_{interval}" / "*.csv").glob(f"{symbol}_{interval}_*.csv"))
                    if files:
                        dfs = []
                        for f in files:
                            df = pd.read_csv(f, parse_dates=['datetime'])
                            dfs.append(df)
                        if dfs:
                            price_df = pd.concat(dfs, ignore_index=True)
                            price_df = price_df.drop_duplicates(subset=['datetime'], keep='first')
                            price_df = price_df.sort_values('datetime').reset_index(drop=True)
                        else:
                            print(f"\n⚠️ 找不到數據文件")
                            return
                    else:
                        print(f"\n⚠️ 找不到數據文件: {data_path}")
                        return
            
            print(f"   📂 使用數據: {data_path}")
            
            # 載入數據
            from data import load_csv
            from strategies import MACrossoverStrategy
            price_df = load_csv(data_path)
            
            # 執行回測 - 直接使用 engine
            from backtest.engine import BacktestEngine
            
            # 創建策略
            strategy_class = MACrossoverStrategy
            strategy = strategy_class(**spec.parameters)
            
            # 生成信號
            signals = strategy.generate_signals(price_df)
            
            # 執行回測
            config = BacktestConfig(
                symbol=intent.get("symbol", "BTCUSDT"),
                interval=intent.get("interval", "30m"),
            )
            engine = BacktestEngine(
                initial_capital=config.initial_capital,
                commission_rate=config.commission_rate,
                position_size=config.position_size,
            )
            backtest_result = engine.run(price_df, signals)
            self.current_result = backtest_result
            
            # 評估
            print("   📈 評估策略...")
            evaluation = self.evaluator.evaluate(backtest_result)
            
            # 顯示結果
            print(f"""
╔══════════════════════════════════════════════════════════╗
║                    📊 回測結果                           ║
╠══════════════════════════════════════════════════════════╣
║  Sharpe Ratio:  {backtest_result.sharpe_ratio:.2f}                        ║
║  Max Drawdown:  {backtest_result.max_drawdown:.1f}%                        ║
║  Win Rate:      {backtest_result.win_rate:.1f}%                        ║
║  Total Trades:  {backtest_result.total_trades}                          ║
║  Profit Factor: {backtest_result.profit_factor:.2f}                        ║
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
                    result=backtest_result,
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
                return
            
        except Exception as e:
            print(f"\n   ❌ 執行出错: {e}")
            import traceback
            traceback.print_exc()


def main():
    """主入口"""
    developer = ConversationalStrategyDeveloper()
    developer.run_interactive()


if __name__ == "__main__":
    main()
