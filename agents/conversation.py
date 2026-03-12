#!/usr/bin/env python3
"""
Conversational Strategy Developer - 對話式策略開發助手

用自然語言與用戶互動，幫助開發交易策略。

使用方式:
    python -m agents.conversation
"""

import os
import sys
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import logging
import pandas as pd

# 確保可以匯入模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents import AgentRole, AgentConfig, get_llm, AGENT_PROMPTS
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


# 對話 Agent 的系統提示詞
CONVERSATION_SYSTEM_PROMPT = """你是一個專業的量化策略開發助手，專門幫助用戶開發比特幣交易策略。

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
- 如果用戶沒有提到優化方式，要詢問偏好
- 執行時會詢問用戶是否需要生成新策略代碼
- 如果需要，會調用 Engineer Agent 生成代碼"""

# Engineer Agent 的系統提示詞 - 負責生成策略代碼
ENGINEER_SYSTEM_PROMPT = """你是一個專業的量化交易策略工程師。

你的職責：
1. 根據策略規格生成完整的 Python 策略代碼
2. 確保代碼繼承正確的 BaseStrategy 類別
3. 實現完整的交易信號邏輯

策略代碼要求：
- 必須繼承 strategies/base.py 中的 BaseStrategy
- 必須實現 required_indicators 屬性
- 必須實現 calculate_signals 方法
- 必須實現 generate_signals 方法（調用 calculate_signals）
- 代碼要可以直接運行

BaseStrategy 結構參考：
```python
from strategies.base import BaseStrategy, SignalType
import pandas as pd

class MyStrategy(BaseStrategy):
    def __init__(self, param1: int = 20, param2: float = 2.0):
        super().__init__(name="MyStrategy")
        self.param1 = param1
        self.param2 = param2
    
    @property
    def required_indicators(self) -> list:
        return ["MA_20", "BBAND_20"]
    
    def calculate_signals(self, data: pd.DataFrame, indicators: dict) -> dict:
        # 計算交易信號
        # 返回格式: {"signal": 1/-1/0, "strength": 0.0~1.0}
        pass
    
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        # 生成完整信號序列
        signals = []
        for i in range(len(data)):
            # 對每根 K 線計算信號
            signals.append(0)  # 0=持有, 1=買入, -1=賣出
        return pd.Series(signals, index=data.index)
```

請生成完整的、可直接運行的策略代碼。"""


class ConversationalStrategyDeveloper:
    """對話式策略開發助手"""
    
    def __init__(self, model: str = "gemini-3-flash-preview", temperature: float = 0.7):
        # LLM 配置（懒加载）
        self._llm = None
        self._llm_config = {
            "model": model,
            "temperature": temperature,
        }
        
        self.developer = StrategyDeveloperAgent()
        self.evaluator = create_strategy_evaluator()
        self.runner = create_backtest_runner()
        self.reporter = ReporterAgent()
        
        # 對話歷史
        self.conversation_history: List[Dict[str, str]] = []
        self.current_strategy: Optional[StrategySpec] = None
        self.current_result: Optional["BacktestReport"] = None
        
        # 策略發想 MD 文件管理
        self.md_dir = Path(__file__).parent.parent / "strategies" / "ideas"
        self.current_md_path: Optional[Path] = None
        
        # 標記是否正在執行
        self.is_executing = False
        
        # 確保有過討論才能執行
        self._has_discussed = False  # 必須經過 LLM 回應一輪
    
    def _save_strategy_code(self, strategy_name: str, code: str) -> str:
        """保存生成的策略代碼到文件"""
        import re
        
        # 從策略名稱生成文件名
        safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', strategy_name)
        safe_name = re.sub(r'_+', '_', safe_name).strip('_')
        
        # 策略目錄
        strategies_dir = Path(__file__).parent.parent / "strategies"
        generated_dir = strategies_dir / "generated"
        generated_dir.mkdir(exist_ok=True)
        
        filename = generated_dir / f"{safe_name}.py"
        
        # 添加頭部註釋
        header = f'''"""Generated Strategy: {strategy_name}

自動生成的策略代碼
"""
'''
        # 寫入文件
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(header + code)
        
        return str(filename)
    
    # ========================================
    # 策略發想 MD 文件管理
    # ========================================
    
    def _load_strategy_md(self) -> tuple:
        """載入策略發想 MD 文件
        
        Returns:
            (md_content, spec): (MD內容, StrategySpec)
        """
        # 確保目錄存在
        self.md_dir.mkdir(parents=True, exist_ok=True)
        
        # 列出所有 MD 文件（排序以確保順序穩定）
        md_files = sorted(self.md_dir.glob("*.md"))
        
        if not md_files:
            return None, None
        
        print("\n📁 找到以下策略發想檔案：")
        for i, f in enumerate(md_files):
            # 讀取標題
            content = f.read_text(encoding='utf-8')
            title = content.split('\n')[0].replace('# ', '') if content else f.stem
            print(f"   {i+1}. {title} ({f.name})")
        
        print(f"   0. 🆕 新建策略發想")
        
        choice = input("\n   請選擇 (編號): ").strip()
        
        if choice == "0" or not md_files:
            return None, None
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(md_files):
                self.current_md_path = md_files[idx]
                content = md_files[idx].read_text(encoding='utf-8')
                spec = self._parse_md_to_spec(content)
                print(f"\n✅ 已載入: {md_files[idx].name}")
                return content, spec
        except ValueError:
            pass
        
        return None, None
    
    def _create_strategy_md(self, name: str) -> Path:
        """建立新的策略發想 MD 文件
        
        Args:
            name: 策略名稱
            
        Returns:
            Path: MD 文件路徑
        """
        self.md_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成文件名
        safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        safe_name = re.sub(r'_+', '_', safe_name).strip('_')
        filename = self.md_dir / f"{safe_name}.md"
        
        # 如果已存在，則覆蓋
        content = f"""# {name}

## 討論歷史

## 策略規格

"""
        filename.write_text(content, encoding='utf-8')
        self.current_md_path = filename
        
        print(f"\n✅ 已建立: {filename.name}")
        return filename
    
    def _update_strategy_md(self, user_input: str = None, assistant_response: str = None, spec: "StrategySpec" = None, generated_file: str = None):
        """更新策略發想 MD 文件
        
        Args:
            user_input: 用戶輸入
            assistant_response: 助手回應
            spec: 策略規格
            generated_file: 生成的程式檔名
        """
        if not self.current_md_path:
            return
        
        content = self.current_md_path.read_text(encoding='utf-8')
        lines = content.split('\n')
        
        # 更新討論歷史
        if user_input:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            lines.append(f"- {timestamp}: 用戶: \"{user_input[:100]}...\"")
        
        if assistant_response:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            lines.append(f"- {timestamp}: 助手: \"{assistant_response[:100]}...\"")
        
        # 更新策略規格
        if spec:
            # 找到策略規格區塊
            spec_start = -1
            for i, line in enumerate(lines):
                if line.strip() == "## 策略規格":
                    spec_start = i
                    break
            
            if spec_start >= 0:
                # 構建新的規格內容
                spec_lines = [
                    f"- 名稱: {spec.name}",
                    f"- 描述: {spec.description}",
                    f"- 指標: {spec.indicators}",
                    f"- 進場規則: {spec.entry_rules or '待確認'}",
                    f"- 出場規則: {spec.exit_rules or '待確認'}",
                    f"- 參數: {spec.parameters}",
                    f"- 時間框架: {spec.timeframe}",
                ]
                
                # 找到下一個區塊
                spec_end = spec_start + 1
                while spec_end < len(lines) and not lines[spec_end].startswith('## '):
                    spec_end += 1
                
                # 替換
                lines = lines[:spec_start+1] + spec_lines + lines[spec_end:]
        
        # 更新生成檔案
        if generated_file:
            # 找到生成檔案區塊
            gen_start = -1
            for i, line in enumerate(lines):
                if line.strip() == "## 生成檔案":
                    gen_start = i
                    break
            
            if gen_start == -1:
                lines.append("\n## 生成檔案")
                lines.append(f"- {generated_file}")
            else:
                lines.append(f"- {generated_file}")
        
        # 寫回文件
        self.current_md_path.write_text('\n'.join(lines), encoding='utf-8')
    
    def _parse_md_to_spec(self, content: str) -> "StrategySpec":
        """從 MD 內容解析出 StrategySpec
        
        Args:
            content: MD 文件內容
            
        Returns:
            StrategySpec: 策略規格
        """
        
        spec_dict = {}
        
        # 解析策略規格區塊
        in_spec = False
        for line in content.split('\n'):
            if line.strip() == "## 策略規格":
                in_spec = True
                continue
            if in_spec and line.startswith('## '):
                break
            if in_spec and line.startswith('- '):
                # 解析 key: value
                if ': ' in line:
                    key, value = line[2:].split(': ', 1)
                    key = key.strip()
                    value = value.strip()

                    if key == "名稱":
                        spec_dict['name'] = value
                    elif key == "描述":
                        spec_dict['description'] = value
                    elif key == "指標":
                        # 解析列表
                        spec_dict['indicators'] = [x.strip() for x in value.strip('[]').split(',')]
                    elif key == "進場規則":
                        spec_dict['entry_rules'] = value
                    elif key.startswith('出台') or key.startswith('出场') or key.startswith('出讓') or key.startswith('\u51FA\u5834') or key.startswith('\u51FA\u573A'):
                        # Support both Simplified (出台/出场) and Traditional (出台/出场) Chinese
                        spec_dict['exit_rules'] = value
                    elif '出' in key and '規則' in key and '進' not in key:
                        # Fallback: any key containing "出" and "規則" but not "進"
                        spec_dict['exit_rules'] = value
                    elif key == "參數":
                        # 解析 dict
                        try:
                            spec_dict['parameters'] = eval(value)
                        except:
                            spec_dict['parameters'] = {}
                    elif key == "時間框架":
                        spec_dict['timeframe'] = value
        
        return StrategySpec(
            name=spec_dict.get('name', '未命名策略'),
            description=spec_dict.get('description', ''),
            indicators=spec_dict.get('indicators', []),
            entry_rules=spec_dict.get('entry_rules', ''),
            exit_rules=spec_dict.get('exit_rules', ''),
            parameters=spec_dict.get('parameters', {}),
            timeframe=spec_dict.get('timeframe', '1h'),
        )
    
    def _load_generated_strategy(self, strategy_name: str, filepath: str):
        """動態加載生成的策略類別"""
        import importlib.util
        import re
        
        try:
            # 從文件名提取類名
            safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', strategy_name)
            safe_name = re.sub(r'_+', '_', safe_name).strip('_')
            module_name = f"strategies.generated.{safe_name}"
            
            # 動態導入
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                
                # 查找策略類別 (繼承 BaseStrategy 的類)
                from strategies.base import BaseStrategy
                for name in dir(module):
                    obj = getattr(module, name)
                    if isinstance(obj, type) and issubclass(obj, BaseStrategy) and obj != BaseStrategy:
                        return obj
            
            return None
        except Exception as e:
            logger.error(f"加載策略失敗: {e}")
            return None
    
    @property
    def llm(self):
        """懒加载 LLM"""
        if self._llm is None:
            try:
                config = AgentConfig(
                    role=AgentRole.CONVERSATIONAL,
                    model=self._llm_config["model"],
                    temperature=self._llm_config["temperature"],
                    max_tokens=2000,
                    system_prompt=CONVERSATION_SYSTEM_PROMPT,
                )
                self._llm = get_llm(config)
            except Exception as e:
                logger.warning(f"LLM 初始化失敗: {e}")
                return None
        return self._llm
    
    def add_message(self, role: str, content: str):
        """添加對話記錄"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
    
    def _save_current_intent(self, message: str):
        """保存當前用戶意圖"""
        self._current_intent = self.parse_user_intent(message)
    
    def _get_last_intent(self) -> Dict[str, Any]:
        """獲取最近保存的用戶意圖"""
        return getattr(self, '_current_intent', None)
    
    def _build_llm_prompt(self, user_input: str) -> str:
        """構建給 LLM 的 prompt，包含對話歷史"""
        # 獲取對話歷史
        history_text = ""
        if self.conversation_history:
            history_text = "\n\n=== 對話歷史 ===\n"
            for msg in self.conversation_history[-6:]:  # 最多保留最近6條
                role_emoji = "👤" if msg["role"] == "user" else "🤖"
                history_text += f"{role_emoji} {msg['content'][:200]}\n"
        
        # 獲取當前策略狀態
        strategy_status = ""
        if self.current_strategy:
            strategy_status = f"\n\n=== 當前策略 ===\n{self.current_strategy}"
        
        prompt = f"""=== 用戶最新輸入 ===
{user_input}
{history_text}
{strategy_status}

請根據以上對話歷史和用戶輸入，決定如何回覆：

1. 如果用戶明確說「好」「可以」「執行」「開始」，表示確認，請回覆「[EXECUTE]」開頭
2. 如果用戶在描述策略需求，請積極詢問細節（週期組合、進出场邏輯、風險偏好等）
3. 如果用戶在回答問題，請確認理解並提出下一個問題或建議
4. 不要直接執行，永遠先確認

回覆格式：
- 如果是要執行：請以「[EXECUTE]」開頭，後面簡要說明你要執行的內容
- 如果是詢問問題：直接輸出問題
- 如果是確認理解：簡短確認並繼續詢問"""
        
        return prompt
    
    def _llm_respond(self, user_input: str) -> str:
        """使用 LLM 生成回應"""
        try:
            prompt = self._build_llm_prompt(user_input)
            response = self.llm.invoke(prompt)
            return response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            logger.warning(f"LLM 調用失敗: {e}")
            # 如果 LLM 失敗，回退到規則方法
            return None
    
    def _should_execute(self, user_input: str, llm_response: str = None) -> bool:
        """判斷是否應該執行"""
        user_input_lower = user_input.lower()
        
        # 必須先經過一輪討論才能執行
        if not self._has_discussed:
            return False
        
        # 明確的確認關鍵詞 - 必須是獨立的確認意圖
        # 只接受明確的確認話語，不接受包含"執行"但意圖不明確的輸入
        confirmation_patterns = [
            "好", "可以", "確認", "ok", "yes", 
            "開始吧", "開始執行", "好阿", "好啊",
            "就這樣做", "就這樣", "開始進行", "執行吧",
            "對", "正確", "沒錯", "好阿", "好啊",
            "就這樣吧", "就這樣就好", "可以了",
        ]
        
        # 嚴格匹配：必須是完整的確認詞，而不是句子中剛好包含這個字
        for pattern in confirmation_patterns:
            # 檢查是否是用戶說的完整確認（前後有邊界）
            import re
            if re.search(rf'\b{re.escape(pattern)}\b', user_input_lower):
                return True
        
        # LLM 建議執行
        if llm_response and llm_response.startswith("[EXECUTE]"):
            return True
        
        return False
    
    def _extract_strategy_from_llm(self, llm_response: str) -> str:
        """從 LLM 回應中提取策略描述"""
        if llm_response and llm_response.startswith("[EXECUTE]"):
            # 移除 [EXECUTE] 標記，獲取執行內容描述
            return llm_response[9:].strip()
        return None
    
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
        elif strategy_type == "bollinger":
            # 布林帶策略 - 根據用戶的盤整盤邏輯
            spec = StrategySpec(
                name=f"{intent['symbol']} BBand策略",
                description=description,
                indicators=["BBand", "MA"],
                parameters={
                    "bband_period": 20,
                    "bband_std": 2.0,
                    "ma_period": 50,
                    "entry_threshold": 1.0,  # 觸及下軌進場
                    "exit_threshold": 1.0,   # 觸及上軌出場
                    "use_ma_confirm": False,
                },
                risk_level="medium",
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
請回复你的答案，或者直接說「好」「可以」或「執行」，我就會著手進行！
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
        
        # ========================================
        # 步驟 1: 詢問新建或載入
        # ========================================
        print("""
📝 請選擇：
   1. 🆕 新建策略發想
   2. 📂 載入既有策略發想
""")
        while True:
            choice = input("   請選擇 (1/2): ").strip()
            if choice in ["1", "2"]:
                break
            print("   ⚠️ 請輸入 1 或 2")
        
        if choice == "1":
            # 新建策略發想
            print("\n📝 請輸入策略名稱（例如：BTCUSDT_軌道策略）")
            strategy_name = input("   > ").strip()
            if not strategy_name:
                strategy_name = "未命名策略"
            self._create_strategy_md(strategy_name)
        else:
            # 載入既有策略
            self._load_strategy_md()
        
        # 顯示當前 MD 內容（如果有）
        if self.current_md_path:
            content = self.current_md_path.read_text(encoding='utf-8')
            # 顯示討論歷史部分
            lines = content.split('\n')
            in_history = False
            print("\n" + "=" * 50)
            print("📜 之前的討論歷史：")
            print("=" * 50)
            for line in lines:
                if line.strip() == "## 討論歷史":
                    in_history = True
                    continue
                if in_history and line.startswith('## '):
                    break
                if in_history:
                    print(f"   {line}")
            print("=" * 50)
        
        # 初始問候
        print("\n👋 你好！請繼續告訴我你想如何調整策略。")
        print("   或者告訴我「好」來執行目前的策略。")
        
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
                
                # 先用 LLM 分析回應
                llm_response = self._llm_respond(user_input)
                
                # 標記已經過一輪討論（只有 LLM 成功回應才算）
                if llm_response:
                    self._has_discussed = True
                    # 更新 MD 文件
                    self._update_strategy_md(user_input=user_input, assistant_response=llm_response)
                
                # 檢查是否應該執行
                if self._should_execute(user_input, llm_response):
                    # 用戶確認，開始執行
                    if self.current_strategy is None:
                        # 從對話歷史中獲取之前的意圖
                        intent = self._get_last_intent()
                        if not intent:
                            # 沒有歷史，需要重新分析
                            intent = self.parse_user_intent(user_input)
                        
                        # 根據意圖生成策略規格
                        spec = self.develop_strategy_from_intent(intent, user_input)
                        self.current_strategy = spec
                    else:
                        spec = self.current_strategy
                    
                    # 執行開發流程
                    self._execute_development(spec, user_input)
                    continue
                
                # LLM 回應
                if llm_response:
                    # 檢查是否是執行標記
                    execute_content = self._extract_strategy_from_llm(llm_response)
                    if execute_content:
                        # LLM 建議執行
                        if self.current_strategy is None:
                            intent = self._get_last_intent() or self.parse_user_intent(user_input)
                            spec = self.develop_strategy_from_intent(intent, user_input)
                            self.current_strategy = spec
                        else:
                            spec = self.current_strategy
                        self._execute_development(spec, user_input)
                        continue
                    
                    # 正常 LLM 回應
                    print(f"\n🤖 {llm_response}")
                    self.add_message("assistant", llm_response)
                else:
                    # LLM 失敗，回退到規則方法
                    discussion = self.discuss_strategy(user_input)
                    print(f"\n🤖 {discussion}")
                    self.add_message("assistant", discussion)
                
                # 保存當前意圖供確認時使用
                self._save_current_intent(user_input)
                
            except KeyboardInterrupt:
                print("\n\n👋 中斷對話，再見！")
                break
            except EOFError:
                break

    def _run_optimization(self, spec, price_df, data_path):
        """執行 Optuna 參數優化"""
        try:
            from strategies import BBandStrategy, MACrossoverStrategy
            from experiments.optuna_search import run_optuna_optimization
            from backtest.engine import BacktestEngine
            from metrics import calculate_metrics
            
            # 根據策略類型選擇
            if "BBand" in spec.indicators:
                strategy_class = BBandStrategy
                param_space = {
                    "bband_period": {"low": 10, "high": 60, "type": "int"},
                    "bband_std": {"low": 1.5, "high": 3.0, "type": "float"},
                    "ma_period": {"low": 20, "high": 200, "type": "int"},
                    "entry_threshold": {"low": 0.0, "high": 0.5, "type": "float"},
                    "exit_threshold": {"low": 0.8, "high": 1.5, "type": "float"},
                }
            else:
                strategy_class = MACrossoverStrategy
                param_space = {
                    "short_window": {"low": 5, "high": 50, "type": "int"},
                    "long_window": {"low": 20, "high": 200, "type": "int"},
                }
            
            print(f"""
╔══════════════════════════════════════════════════════════╗
║              🧠 Optuna 參數優化                         ║
╠══════════════════════════════════════════════════════════╣
║  策略: {strategy_class.__name__:<40}║
║  試驗次數: 50                                           ║
║  優化目標: Sharpe Ratio                                 ║
╚══════════════════════════════════════════════════════════╝
""")
            
            # 執行優化
            result = run_optuna_optimization(
                data=price_df,
                strategy_class=strategy_class,
                param_space=param_space,
                objective="sharpe_ratio",
                n_trials=50,
                direction="maximize",
                show_progress=True,
                max_drawdown_constraint=-0.5,  # 最大回撤約束 -50%
            )
            
            if result.get("best_value"):
                print(f"""
╔══════════════════════════════════════════════════════════╗
║              ✅ 優化完成                                 ║
╠══════════════════════════════════════════════════════════╣
║  最佳 Sharpe Ratio: {result['best_value']:.4f}                       ║
║  最佳參數:                                               ║""")
                
                for k, v in result.get("best_params", {}).items():
                    print(f"║    {k}: {v}")
                
                print("""╚══════════════════════════════════════════════════════════╝
""")
                
                # 使用最佳參數重新回測
                best_strategy = strategy_class(**result["best_params"])
                signals = best_strategy.generate_signals(price_df)
                
                engine = BacktestEngine(
                    initial_capital=10000,
                    commission_rate=0.001,
                )
                backtest_result = engine.run(price_df, signals)
                metrics = calculate_metrics(backtest_result)
                
                print(f"""
╔══════════════════════════════════════════════════════════╗
║            📊 優化後回測結果                            ║
╠══════════════════════════════════════════════════════════╣
║  Sharpe Ratio:  {metrics['sharpe_ratio']:.2f}                        ║
║  Max Drawdown:  {metrics['max_drawdown']*100:.1f}%                        ║
║  Win Rate:      {metrics['win_rate']*100:.1f}%                        ║
║  Total Trades:  {backtest_result.total_trades}                          ║
║  Profit Factor: {metrics['profit_factor']:.2f}                        ║
╚══════════════════════════════════════════════════════════╝
""")
                
        except Exception as e:
            print(f"\n⚠️ 優化失敗: {e}")
            import traceback
            traceback.print_exc()
    
    def _execute_development(self, spec, user_input: str = ""):
        """執行策略開發流程"""
        try:
            # 使用 spec 中已有的信息，而不是重新解析
            interval = spec.timeframe or "1h"
            symbol = spec.name.split()[0] if spec.name else "BTCUSDT"  # 從名稱提取交易對
            
            # 嘗試載入數據 - 支援多個可能路徑
            project_root = Path(__file__).parent.parent
            
            # 搜索數據文件
            possible_paths = [
                project_root / "data" / f"{symbol}_{interval}.csv",
                project_root / "data" / symbol / f"{symbol}_{interval}.csv",
                project_root / ".." / "data" / f"{symbol}_{interval}.csv",
            ]
            
            data_path = None
            for path in possible_paths:
                if path.exists():
                    data_path = str(path)
                    break
            
            # 如果沒找到，搜索所有 CSV 文件
            if not data_path:
                csv_files = list(project_root.glob(f"**/{symbol}_{interval}.csv"))
                if csv_files:
                    data_path = str(csv_files[0])
            
            if not data_path or not os.path.exists(data_path):
                print(f"\n⚠️ 找不到數據文件!")
                print(f"   嘗試的路徑:")
                for p in possible_paths:
                    print(f"   - {p}")
                print(f"\n   請確認數據文件路徑，或先下載數據")
                return
            
            print(f"   📂 使用數據: {data_path}")
            
            # 載入數據
            from data import load_csv
            price_df = load_csv(data_path)
            
            print(f"   📊 數據載入成功: {len(price_df)} 行")
            
            # ========================================
            # 步驟 1: 詢問是否生成新策略代碼
            # ========================================
            print("""
   是否需要生成新的策略代碼？
   y) 是，讓 Engineer Agent 根據需求生成策略代碼
   n) 否，使用現有策略
""")
            
            generate_code = input("   > ").strip().lower()
            
            strategy_class = None
            
            if generate_code == "y":
                print("""
╔══════════════════════════════════════════════════════════╗
║              💻 Engineer Agent 生成策略代碼            ║
╚══════════════════════════════════════════════════════════╝
""")
                
                # 獲取 MD 上下文
                md_context = None
                if self.current_md_path:
                    md_context = self.current_md_path.read_text(encoding='utf-8')
                
                # 生成策略代碼（傳入 MD 上下文）
                strategy_code = self.developer.generate_strategy_code(spec, md_context=md_context)
                
                if strategy_code:
                    # 保存代碼到文件
                    strategy_filename = self._save_strategy_code(spec.name, strategy_code)
                    print(f"   ✅ 代碼已生成並保存到: {strategy_filename}")
                    
                    # 更新 MD 文件
                    self._update_strategy_md(spec=spec, generated_file=strategy_filename)
                    
                    # 動態加載策略
                    strategy_class = self._load_generated_strategy(spec.name, strategy_filename)
                    
                    if strategy_class:
                        print(f"   ✅ 策略加載成功: {strategy_class.__name__}")
                    else:
                        print("   ⚠️ 代碼加載失敗，回退到現有策略")
                        strategy_class = None
                else:
                    print("   ⚠️ 代碼生成失敗，回退到現有策略")
            
            # ========================================
            # 步驟 2: 如果沒有生成新代碼，使用現有策略
            # ========================================
            if strategy_class is None:
                from strategies import BBandStrategy, MACrossoverStrategy
                
                # 根據策略類型選擇現有策略
                if "BBand" in spec.indicators:
                    strategy_class = BBandStrategy
                else:
                    strategy_class = MACrossoverStrategy
            
            # 執行回測 - 直接使用 engine
            from backtest.engine import BacktestEngine
            
            # 創建策略
            strategy = strategy_class(**spec.parameters)
            
            # 生成信號
            print(f"   ⚙️ 策略: {strategy_class.__name__}")
            print(f"   📐 參數: {spec.parameters}")
            signals = strategy.generate_signals(price_df)
            
            # 執行回測
            config = BacktestConfig(
                symbol=symbol,
                interval=interval,
            )
            engine = BacktestEngine(
                initial_capital=config.initial_capital,
                commission_rate=config.commission_rate,
                position_size=config.position_size,
            )
            backtest_result = engine.run(price_df, signals)
            self.current_result = backtest_result
            
            # 計算績效指標
            from metrics import calculate_metrics
            metrics = calculate_metrics(backtest_result)
            
            # 評估
            print("   📈 評估策略...")
            evaluation = self.evaluator.evaluate(backtest_result, metrics)
            
            # 顯示結果
            print(f"""
╔══════════════════════════════════════════════════════════╗
║                    📊 回測結果                           ║
╠══════════════════════════════════════════════════════════╣
║  Sharpe Ratio:  {metrics['sharpe_ratio']:.2f}                        ║
║  Max Drawdown:  {metrics['max_drawdown']*100:.1f}%                        ║
║  Win Rate:      {metrics['win_rate']*100:.1f}%                        ║
║  Total Trades:  {backtest_result.total_trades}                          ║
║  Profit Factor: {metrics['profit_factor']:.2f}                        ║
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
            
            # 詢問是否進行參數優化
            print("""
   是否需要進行參數優化？
   y) 是，使用 Optuna 自動優化參數
   n) 否
""")
            
            do_optimize = input("   > ").strip().lower()
            
            if do_optimize == "y":
                self._run_optimization(spec, price_df, data_path)
            
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
