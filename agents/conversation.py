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
import argparse
import inspect
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
from agents.strategy_rd_workflow import (
    StrategyRDWorkflow,
    RDConfig,
    HumanDecision,
    HumanDecisionAction,
)

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
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        # 生成完整信號序列
        signals = []
        for i in range(len(data)):
            # 對每根 K 線計算信號
            signals.append(0)  # 0=持有, 1=買入, -1=賣出
        df = data.copy()
        if "datetime" not in df.columns:
            df["datetime"] = df.index
        df["signal"] = signals
        return df
```

請生成完整的、可直接運行的策略代碼。"""


class ConversationalStrategyDeveloper:
    """對話式策略開發助手"""
    
    def __init__(
        self,
        model: str = "gemini-3-flash-preview",
        temperature: float = 0.7,
        engineer_model: Optional[str] = None,
        evaluator_model: Optional[str] = None,
        reporter_model: Optional[str] = None,
    ):
        # LLM 配置（懒加载）
        self._llm = None
        self._llm_config = {
            "model": model,
            "temperature": temperature,
        }

        self.engineer_model = engineer_model or model
        self.evaluator_model = evaluator_model or model
        self.reporter_model = reporter_model or model

        self.developer = StrategyDeveloperAgent(model=self.engineer_model)
        self.evaluator = create_strategy_evaluator(model=self.evaluator_model)
        self.runner = create_backtest_runner()
        self.reporter = ReporterAgent(model=self.reporter_model)
        
        # 對話歷史
        self.conversation_history: List[Dict[str, str]] = []
        self.current_strategy: Optional[StrategySpec] = None
        self.current_result: Optional["BacktestReport"] = None
        self.current_report = None
        
        # 策略發想 MD 文件管理
        self.md_dir = Path(__file__).parent.parent / "strategies" / "ideas"
        self.current_md_path: Optional[Path] = None
        
        # 標記是否正在執行
        self.is_executing = False
        self._last_strategy_class = None
        
        # 確保有過討論才能執行
        self._has_discussed = False  # 必須經過 LLM 回應一輪

    def _prompt_human_checkpoint(self, context: Dict[str, Any]) -> HumanDecision:
        """在每輪回測後詢問 human checkpoint，決定是否繼續 loop。"""
        report = context["report"]
        proposed_action = context["proposed_action"]

        print("\n" + "=" * 60)
        print("🧑 Human Checkpoint")
        print("=" * 60)
        print(f"   策略: {report.strategy_name}")
        print(f"   收益率: {report.total_return:.2f}%")
        print(f"   Sharpe: {report.sharpe_ratio:.2f}")
        print(f"   回撤: {report.max_drawdown:.2f}%")
        print(f"   勝率: {report.win_rate:.2f}%")
        print(f"   Agent 建議: {proposed_action.value}")
        print("""
   請選擇下一步：
   accept   接受當前策略並停止 loop
   continue 繼續沿目前方向迭代
   revise   針對目前策略修正
   pivot    改策略方向（下一輪你可以先更新 MD/spec）
   stop     停止目前 loop
""")

        while True:
            action = input("   action > ").strip().lower() or proposed_action.value
            try:
                normalized_action = HumanDecisionAction(action)
                break
            except ValueError:
                print("   ⚠️ 請輸入 accept / continue / revise / pivot / stop")

        rationale = input("   rationale > ").strip()
        next_focus_raw = input("   next focus（可留白，用逗號分隔）> ").strip()
        next_focus = [item.strip() for item in next_focus_raw.split(",") if item.strip()]

        return HumanDecision(
            action=normalized_action,
            rationale=rationale,
            next_focus=next_focus,
        )
    
    def _extract_python_code(self, content: str) -> str:
        """從 LLM 回應中提取可解析的 Python 程式碼。"""
        import ast

        if not content:
            return ""

        candidates = []

        stripped = content.strip()
        if stripped:
            candidates.append(stripped)

        fenced_blocks = re.findall(r"```(?:python)?\s*(.*?)```", content, flags=re.DOTALL)
        candidates.extend(block.strip() for block in fenced_blocks if block.strip())

        lines = content.splitlines()
        start_idx = None
        for idx, line in enumerate(lines):
            normalized = line.lstrip()
            if normalized.startswith(("import ", "from ", "class ")):
                start_idx = idx
                break

        if start_idx is not None:
            code_lines = self._collect_code_lines(lines[start_idx:])
            if code_lines:
                candidates.append("\n".join(code_lines).strip())

        seen = set()
        for candidate in candidates:
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            trimmed = self._trim_to_valid_python(candidate)
            if trimmed:
                return trimmed

        return stripped

    def _collect_code_lines(self, lines: List[str]) -> List[str]:
        """從混合輸出中收集看起來像 Python 的程式碼區塊。"""
        collected: List[str] = []
        started = False

        for line in lines:
            stripped = line.strip()
            normalized = line.lstrip()

            if not started and normalized.startswith(("import ", "from ", "class ")):
                started = True

            if not started:
                continue

            if self._looks_like_non_code_boundary(line):
                break

            collected.append(line)

        while collected and not collected[-1].strip():
            collected.pop()

        return collected

    def _looks_like_non_code_boundary(self, line: str) -> bool:
        """判斷一行是否更像是敘述文字而不是 Python 程式碼。"""
        stripped = line.strip()
        normalized = line.lstrip()

        if not stripped:
            return False

        if "HTTP Request:" in stripped:
            return True

        if re.match(r"^\d+\.\s", stripped):
            return True

        if re.match(r"^[-*]\s", stripped):
            return True

        if re.match(r"^[\u4e00-\u9fff]", stripped):
            return True

        allowed_prefixes = (
            "from ", "import ", "class ", "def ", "@", "#",
            "if ", "elif ", "else", "for ", "while ", "try", "except", "finally",
            "with ", "return", "pass", "break", "continue", "raise", "yield", "assert",
            '"""', "'''", ")", "]", "}", ",",
        )
        if normalized.startswith(allowed_prefixes):
            return False

        if normalized.startswith(("self.", "signals", "signal", "result", "data", "df_", "bb_")):
            return False

        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*=", normalized):
            return False

        if line.startswith((" ", "\t")):
            return False

        return True

    def _trim_to_valid_python(self, candidate: str) -> str:
        """從候選內容尾端回退，找到可解析的 Python 程式碼。"""
        import ast

        lines = candidate.splitlines()
        for end in range(len(lines), 0, -1):
            snippet = "\n".join(lines[:end]).strip()
            if not snippet:
                continue
            try:
                ast.parse(snippet)
                return snippet
            except SyntaxError:
                continue

        return ""

    def _save_strategy_code(self, strategy_name: str, code: str) -> Optional[str]:
        """保存生成的策略代碼到文件。"""
        import re
        import ast
        
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
        
        code = self._extract_python_code(code)

        # 驗證代碼語法
        full_code = header + code
        try:
            ast.parse(full_code)
            if not self._is_valid_strategy_code(full_code):
                print("   ❌ 代碼雖可解析，但缺少有效的策略類別或核心方法")
                return None
            print("   ✅ 代碼語法驗證通過")
        except SyntaxError as e:
            print(f"   ⚠️ 代碼語法有誤: {e}")
            print("   嘗試修復...")
            
            # 嘗試自動修復常見問題
            # 1. 移除可能的 markdown 標記
            code = code.replace("```python", "").replace("```", "")
            
            # 2. 修復未閉合的三引號字符串（docstring）
            lines = code.split('\n')
            fixed_lines = []
            in_docstring = False
            docstring_start = None
            
            for i, line in enumerate(lines):
                if '"""' in line:
                    count = line.count('"""')
                    if count == 1:
                        if not in_docstring:
                            # Docstring 開始
                            in_docstring = True
                            docstring_start = i
                            fixed_lines.append(line)
                        else:
                            # Docstring 結束
                            in_docstring = False
                            fixed_lines.append(line)
                    else:
                        # 偶數個，直接添加
                        fixed_lines.append(line)
                else:
                    fixed_lines.append(line)
            
            # 如果還在 docstring 裡，添加關閉標記
            if in_docstring and docstring_start is not None:
                fixed_lines.insert(docstring_start + 1, '"""')
                print("   🔧 已修復未閉合的三引號/docstring")
            
            code = '\n'.join(fixed_lines)
            
            # 3. 修復未閉合的單引號字符串
            single_quote_count = code.count("'") - code.count("\\'")
            if single_quote_count % 2 == 1:
                code = code + "'"
                print("   🔧 已修復未閉合的單引號")
            
            # 4. 移除行內的 markdown 殘餘
            lines = code.split('\n')
            fixed_lines = []
            for line in lines:
                line = re.sub(r'^```\w*$', '', line)
                line = re.sub(r'^```$', '', line)
                fixed_lines.append(line)
            code = '\n'.join(fixed_lines)
            
            full_code = header + code
            
            try:
                ast.parse(full_code)
                if not self._is_valid_strategy_code(full_code):
                    print("   ❌ 修復後仍缺少有效的策略類別或核心方法")
                    return None
                print("   ✅ 代碼已修復並通過驗證")
            except SyntaxError as e2:
                print(f"   ❌ 無法修復語法錯誤: {e2}")
                # 嘗試最保守的方法：移除所有三引號，只保留代碼
                # 這是最後的補救措施
                print("   🔄 嘗試最後補救...")
                # 移除 markdown 代碼塊
                code = re.sub(r'^```.*', '', code, flags=re.MULTILINE)
                code = re.sub(r'```$', '', code, flags=re.MULTILINE)
                # 嘗試找類定義
                class_match = re.search(r'class\s+(\w+)\([^)]+\):', code)
                if class_match:
                    print(f"   ⚠️ 找到類定義: {class_match.group(1)}，使用最小化修復")
                    # 添加最小實現
                    code = code.strip()
                    if 'def generate_signals' not in code:
                        code += '\n\n    def generate_signals(self, data):\n        import pandas as pd\n        from strategies.base import SignalType\n        df = data.copy()\n        if "datetime" not in df.columns:\n            df["datetime"] = df.index\n        df["signal"] = SignalType.HOLD\n        return df'
                    full_code = header + code
                    try:
                        ast.parse(full_code)
                        print("   ✅ 補救成功")
                    except:
                        pass
                
                print("   ❌ 代碼仍無法修復，放棄保存生成檔案")
                return None
        
        # 寫入文件
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(full_code)
        
        return str(filename)

    def _should_use_local_template(self, spec: "StrategySpec") -> bool:
        """判斷是否應優先使用本地模板生成策略。"""
        indicators = self._normalized_indicator_set(spec)
        params = spec.parameters or {}
        return (
            "bband" in indicators
            and "higher_timeframe" in params
            and "entry_timeframe" in params
        )

    def _normalized_indicator_set(self, spec: "StrategySpec") -> set[str]:
        """統一清理 indicator 名稱，避免 MD 解析殘留引號或大小寫造成判斷失敗。"""
        normalized = set()
        for indicator in (spec.indicators or []):
            value = str(indicator).strip().strip("'\"").strip()
            if value:
                normalized.add(value.lower())
        return normalized

    def _generate_local_template_strategy(self, spec: "StrategySpec") -> str:
        """使用本地模板生成穩定的策略程式碼。"""
        class_name = re.sub(r'[^a-zA-Z0-9_]', '', spec.name.title().replace(" ", "")) or "GeneratedStrategy"
        if not class_name.endswith("Strategy"):
            class_name += "Strategy"

        params = spec.parameters or {}
        bb_period = int(params.get("bb_period", 20))
        bb_std = float(params.get("bb_std", 2.0))
        volume_ma_period = int(params.get("volume_ma_period", 20))
        volume_multiplier = float(params.get("volume_multiplier", 2.0))
        stop_loss_pct = float(params.get("stop_loss_pct", 0.03))
        higher_timeframe = str(params.get("higher_timeframe", "4h"))
        entry_timeframe = str(params.get("entry_timeframe", spec.timeframe or "1h"))
        strategy_name = spec.name.replace('"', '\\"')

        return f'''from strategies.base import BaseStrategy, SignalType
import pandas as pd
import numpy as np


class {class_name}(BaseStrategy):
    """Local template strategy generated from strategy spec.

    Note:
        The current backtest engine is long-only. This template implements the
        long setup of the multi-timeframe BBand strategy and exits on upper band
        touch or fixed stop loss.
    """

    def __init__(
        self,
        bb_period: int = {bb_period},
        bb_std: float = {bb_std},
        volume_ma_period: int = {volume_ma_period},
        volume_multiplier: float = {volume_multiplier},
        stop_loss_pct: float = {stop_loss_pct},
        higher_timeframe: str = "{higher_timeframe}",
        entry_timeframe: str = "{entry_timeframe}",
        name: str = "{strategy_name}",
    ):
        super().__init__(name=name)
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.volume_ma_period = volume_ma_period
        self.volume_multiplier = volume_multiplier
        self.stop_loss_pct = stop_loss_pct
        self.higher_timeframe = higher_timeframe
        self.entry_timeframe = entry_timeframe
        self.required_indicators = [
            f"BBand_{{bb_period}}_{{bb_std}}",
            f"Volume_MA_{{volume_ma_period}}",
        ]

    def calculate_signals(self, data: pd.DataFrame, indicators: dict) -> dict:
        row = data.iloc[-1]
        long_setup = bool(row.get("higher_long_setup", False))
        touch_lower = bool(row.get("touch_lower", False))
        touch_upper = bool(row.get("touch_upper", False))
        volume_ok = bool(row.get("volume_ok", False))
        in_position = bool(row.get("in_position", False))
        stop_loss_hit = bool(row.get("stop_loss_hit", False))

        if in_position and (touch_upper or stop_loss_hit):
            return {{"signal": SignalType.SELL, "strength": 1.0}}
        if (not in_position) and long_setup and touch_lower and volume_ok:
            return {{"signal": SignalType.BUY, "strength": 1.0}}
        return {{"signal": SignalType.HOLD, "strength": 0.0}}

    def _calc_bbands(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["bb_middle"] = df["close"].rolling(window=self.bb_period).mean()
        rolling_std = df["close"].rolling(window=self.bb_period).std()
        df["bb_upper"] = df["bb_middle"] + (rolling_std * self.bb_std)
        df["bb_lower"] = df["bb_middle"] - (rolling_std * self.bb_std)
        return df

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)

        higher_df = (
            df.set_index("datetime")
            .resample(self.higher_timeframe)
            .agg({{
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }})
            .dropna()
            .reset_index()
        )
        higher_df = self._calc_bbands(higher_df)
        higher_df["higher_long_setup"] = higher_df["low"] <= higher_df["bb_lower"]
        higher_df = higher_df[["datetime", "higher_long_setup"]]

        df = self._calc_bbands(df)
        df["volume_ma"] = df["volume"].rolling(window=self.volume_ma_period).mean()
        df["volume_ok"] = df["volume"] >= (df["volume_ma"] * self.volume_multiplier)
        df["touch_lower"] = df["low"] <= df["bb_lower"]
        df["touch_upper"] = df["high"] >= df["bb_upper"]

        df = pd.merge_asof(
            df.sort_values("datetime"),
            higher_df.sort_values("datetime"),
            on="datetime",
            direction="backward",
        )
        df["higher_long_setup"] = df["higher_long_setup"].fillna(False)
        df["signal"] = SignalType.HOLD
        df["in_position"] = False
        df["stop_loss_hit"] = False

        in_position = False
        entry_price = np.nan

        for i in range(len(df)):
            if pd.isna(df.loc[i, "bb_lower"]) or pd.isna(df.loc[i, "bb_upper"]) or pd.isna(df.loc[i, "volume_ma"]):
                continue

            stop_loss_hit = False
            if in_position:
                stop_price = entry_price * (1 - self.stop_loss_pct)
                stop_loss_hit = df.loc[i, "low"] <= stop_price

            df.loc[i, "in_position"] = in_position
            df.loc[i, "stop_loss_hit"] = stop_loss_hit

            result = self.calculate_signals(df.iloc[: i + 1], {{}})
            df.loc[i, "signal"] = result["signal"]

            if result["signal"] == SignalType.BUY:
                in_position = True
                entry_price = df.loc[i, "close"]
            elif result["signal"] == SignalType.SELL:
                in_position = False
                entry_price = np.nan

        return df[["datetime", "open", "high", "low", "close", "volume", "signal"]]
'''
    
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
                        spec_dict['indicators'] = [
                            x.strip().strip("'\"").strip()
                            for x in value.strip('[]').split(',')
                            if x.strip()
                        ]
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
    
    def _fix_syntax_errors(self, code: str) -> str:
        """修復常見的語法錯誤"""
        import re
        
        # 1. 修復未閉合的三引號字符串（docstring）
        lines = code.split('\n')
        fixed_lines = []
        in_docstring = False
        docstring_start = None
        
        for i, line in enumerate(lines):
            if '"""' in line:
                count = line.count('"""')
                if count == 1:
                    if not in_docstring:
                        # Docstring 開始
                        in_docstring = True
                        docstring_start = i
                        fixed_lines.append(line)
                    else:
                        # Docstring 結束
                        in_docstring = False
                        fixed_lines.append(line)
                else:
                    # 偶數個，直接添加
                    fixed_lines.append(line)
            else:
                fixed_lines.append(line)
        
        # 如果還在 docstring 裡，添加關閉標記
        if in_docstring and docstring_start is not None:
            fixed_lines.insert(docstring_start + 1, '"""')
        
        code = '\n'.join(fixed_lines)
        
        # 2. 修復未閉合的單引號字符串
        single_quote_count = code.count("'") - code.count("\\'")
        if single_quote_count % 2 == 1:
            code = code + "'"
        
        # 3. 移除行內的 markdown 殘餘
        lines = code.split('\n')
        fixed_lines = []
        for line in lines:
            line = re.sub(r'^```\w*$', '', line)
            line = re.sub(r'^```$', '', line)
            fixed_lines.append(line)
        code = '\n'.join(fixed_lines)

        return code

    def _is_valid_strategy_code(self, code: str) -> bool:
        """檢查內容是否為可載入的策略程式碼。"""
        import ast

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return False

        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue

            method_names = {
                child.name
                for child in node.body
                if isinstance(child, ast.FunctionDef)
            }
            if "generate_signals" in method_names or "calculate_signals" in method_names:
                return True

        return False

    def _instantiate_strategy(self, strategy_class, parameters: Dict[str, Any]):
        """根據策略類別的 __init__ 簽名安全地建立實例。"""
        parameters = parameters or {}

        try:
            init_sig = inspect.signature(strategy_class.__init__)
        except (TypeError, ValueError):
            init_sig = None

        if init_sig is None:
            return strategy_class(**parameters)

        accepted_params = {}
        accepts_var_kwargs = False

        for name, param in init_sig.parameters.items():
            if name == "self":
                continue
            if param.kind == inspect.Parameter.VAR_KEYWORD:
                accepts_var_kwargs = True
                break
            if param.kind in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            ) and name in parameters:
                accepted_params[name] = parameters[name]

        if accepts_var_kwargs:
            accepted_params = dict(parameters)

        ignored_params = {
            key: value for key, value in parameters.items()
            if key not in accepted_params
        }
        if ignored_params:
            print(f"   ⚠️ 忽略不支援的策略參數: {ignored_params}")

        return strategy_class(**accepted_params)

    def _extract_symbol_from_spec(self, spec: "StrategySpec") -> str:
        """從策略規格或檔名中提取交易對。"""
        candidates = []

        if spec and spec.name:
            candidates.append(spec.name)
        if self.current_md_path:
            candidates.append(self.current_md_path.stem)

        for candidate in candidates:
            match = re.search(r"\b([A-Z]{2,10}USDT)\b", candidate.upper())
            if match:
                return match.group(1)

            match = re.search(r"([A-Z]{2,10}_?USDT)", candidate.upper())
            if match:
                return match.group(1).replace("_", "")

        return "BTCUSDT"
    
    def _load_generated_strategy(self, strategy_name: str, filepath: str):
        """動態加載生成的策略類別"""
        import importlib.util
        import re
        import ast
        
        try:
            # 嘗試修復文件中的語法錯誤
            with open(filepath, 'r', encoding='utf-8') as f:
                code = f.read()
            
            # 嘗試解析，如果失敗則嘗試修復
            try:
                ast.parse(code)
            except SyntaxError as e:
                print(f"   ⚠️ 文件語法有誤，嘗試修復: {e}")
                code = self._fix_syntax_errors(code)
                if not self._is_valid_strategy_code(code):
                    print("   ❌ 修復後仍不是有效的策略程式碼")
                    return None

                # 寫回修復後的代碼
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(code)
                print("   🔧 已修復並保存")
            
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
                from strategies.base import BaseStrategy, SignalType
                original_class = None
                for name in dir(module):
                    obj = getattr(module, name)
                    if isinstance(obj, type) and issubclass(obj, BaseStrategy) and obj != BaseStrategy:
                        original_class = obj
                        break
                
                if original_class is None:
                    print("   ⚠️ 生成檔案中找不到 BaseStrategy 子類，回退到現有策略")
                    return None
                
                # 檢查必要方法
                has_own_generate = 'generate_signals' in original_class.__dict__
                has_own_calculate = 'calculate_signals' in original_class.__dict__
                has_own_required = 'required_indicators' in original_class.__dict__

                if not has_own_generate and not has_own_calculate:
                    print("   ⚠️ 生成策略缺少核心方法，回退到現有策略")
                    return None
                
                if not has_own_generate:
                    print(f"   ⚠️ 缺少 generate_signals，添加默認實現")
                    
                    # 動態創建新類，繼承原始類並實現 generate_signals
                    def default_generate_signals(self, data):
                        if hasattr(self, "calculate_signals"):
                            signals = []
                            for i in range(len(data)):
                                row_data = data.iloc[: i + 1]
                                result = self.calculate_signals(row_data, {})
                                signals.append(result.get("signal", SignalType.HOLD))
                            df = data.copy()
                            if "datetime" not in df.columns:
                                df["datetime"] = df.index
                            df["signal"] = signals
                            return df
                        df = data.copy()
                        if "datetime" not in df.columns:
                            df["datetime"] = df.index
                        df["signal"] = SignalType.HOLD
                        return df
                    
                    # 創建新的子類
                    NewClass = type(
                        original_class.__name__ + '_WithSignals',
                        (original_class,),
                        {'generate_signals': default_generate_signals}
                    )

                    if not has_own_required:
                        NewClass.required_indicators = property(lambda self: [])
                    return NewClass
                
                return original_class
            
            return None
        except Exception as e:
            logger.error(f"加載策略失敗: {e}")
            return None

    def _generated_strategy_path(self, strategy_name: str) -> Path:
        """取得生成策略檔案路徑。"""
        safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', strategy_name)
        safe_name = re.sub(r'_+', '_', safe_name).strip('_')
        return Path(__file__).parent.parent / "strategies" / "generated" / f"{safe_name}.py"
    
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
        print(f"   對話模型: {self._llm_config['model']}")
        print(f"   Engineer 模型: {self.engineer_model}")
        print(f"   Evaluator 模型: {self.evaluator_model}")
        print(f"   Reporter 模型: {self.reporter_model}")
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
            content, spec = self._load_strategy_md()
            if content is None:
                # 沒有找到現有檔案，提示用戶
                print("\n📁 尚未找到任何策略發想檔案。")
                print("   讓我幫你建立一個新的策略發想。")
                print("\n📝 請輸入策略名稱（例如：BTCUSDT_軌道策略）")
                strategy_name = input("   > ").strip()
                if not strategy_name:
                    strategy_name = "未命名策略"
                self._create_strategy_md(strategy_name)
            else:
                self.current_strategy = spec
        
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

    def _run_optimization(self, spec, price_df, data_path, strategy_class=None):
        """執行 Optuna 參數優化"""
        try:
            normalized_indicators = self._normalized_indicator_set(spec)
            from strategies import BBandStrategy, MACrossoverStrategy
            from experiments.optuna_search import run_optuna_optimization
            from backtest.engine import BacktestEngine
            from metrics import calculate_metrics
            
            # 根據當前實際使用的策略類型選擇
            if strategy_class is None:
                if "bband" in normalized_indicators:
                    strategy_class = BBandStrategy
                else:
                    strategy_class = MACrossoverStrategy

            if (
                strategy_class is MACrossoverStrategy
                and spec.parameters
                and "higher_timeframe" in spec.parameters
                and "entry_timeframe" in spec.parameters
            ):
                generated_path = self._generated_strategy_path(spec.name)
                if generated_path.exists():
                    loaded_class = self._load_generated_strategy(spec.name, str(generated_path))
                    if loaded_class is not None:
                        strategy_class = loaded_class

            strategy_name = getattr(strategy_class, "__name__", "")
            if strategy_name == "Btcusdt_MaStrategy" or (
                spec.parameters
                and "higher_timeframe" in spec.parameters
                and "entry_timeframe" in spec.parameters
            ):
                param_space = {
                    "bb_period": {"low": 10, "high": 40, "type": "int"},
                    "bb_std": {"low": 1.5, "high": 3.0, "type": "float"},
                    "volume_ma_period": {"low": 10, "high": 40, "type": "int"},
                    "volume_multiplier": {"low": 1.2, "high": 3.0, "type": "float"},
                    "stop_loss_pct": {"low": 0.01, "high": 0.05, "type": "float"},
                }
            elif "bband" in normalized_indicators or strategy_class is BBandStrategy:
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
            normalized_indicators = self._normalized_indicator_set(spec)
            # 使用 spec 中已有的信息，而不是重新解析
            interval = spec.timeframe or "1h"
            symbol = self._extract_symbol_from_spec(spec)
            
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
║          🔁 Agentic Strategy R&D Loop 啟動             ║
╚══════════════════════════════════════════════════════════╝
""")

                md_context = None
                if self.current_md_path:
                    md_context = self.current_md_path.read_text(encoding='utf-8')

                workflow = StrategyRDWorkflow(
                    RDConfig(
                        symbol=symbol,
                        interval=interval,
                        initial_capital=10000.0,
                        data_dir=str(project_root / "data"),
                        report_dir="reports",
                        max_iterations=3,
                    )
                )
                report = workflow.run(
                    market_analysis=user_input or f"{symbol} {interval}",
                    initial_strategy=spec,
                    md_context=md_context,
                    human_decision_provider=self._prompt_human_checkpoint,
                )
                if workflow.route_decision is not None:
                    print(
                        f"   🧭 策略路由: {workflow.route_decision.route.value} "
                        f"({workflow.route_decision.strategy_family})"
                    )

                self.current_strategy = workflow.current_strategy or spec
                self.current_report = report

                if workflow.iterations:
                    last_iteration = workflow.iterations[-1]
                    self.current_result = last_iteration.get("backtest_report")
                    validated_path = workflow.current_validated_code_path
                    if validated_path:
                        strategy_class = workflow._load_strategy_class(validated_path)
                        self._last_strategy_class = strategy_class

                if report:
                    print(workflow.reporter.format_report_compact(report))

                    if workflow.current_validated_code_path:
                        print(f"   🧾 最後一輪代碼: {workflow.current_validated_code_path}")
                        self._update_strategy_md(
                            spec=self.current_strategy,
                            generated_file=workflow.current_validated_code_path,
                        )
                else:
                    print("   ⚠️ Agentic loop 未產出報告")
                    if workflow.iterations:
                        last_validation = workflow.iterations[-1].get("validation")
                        if last_validation and getattr(last_validation, "issues", None):
                            print("   🔎 最後一輪驗證失敗原因:")
                            for issue in last_validation.issues[:5]:
                                print(f"      - {issue}")
                    if workflow.current_code_path:
                        print(f"   🧾 最後一輪代碼: {workflow.current_code_path}")

                    if self._should_use_local_template(spec):
                        print("   🛠️ 改用本地模板生成同規格策略，避免再退回不相干的既有策略")
                        saved_path = self._save_strategy_code(
                            spec.name,
                            self._generate_local_template_strategy(spec),
                        )
                        if saved_path:
                            print(f"   🧾 本地模板代碼: {saved_path}")
                            strategy_class = self._load_generated_strategy(spec.name, saved_path)
                            self._last_strategy_class = strategy_class
                            self._update_strategy_md(
                                spec=spec,
                                generated_file=saved_path,
                            )
                    elif generate_code == "y":
                        print("   ❌ 本次停止執行：未取得可驗證的策略代碼。")
                        return
            
            # ========================================
            # 步驟 2: 如果沒有生成新代碼，使用現有策略
            # ========================================
            if strategy_class is None and generate_code != "y":
                generated_path = self._generated_strategy_path(spec.name)
                if generated_path.exists():
                    print(f"   📦 載入既有生成策略: {generated_path}")
                    strategy_class = self._load_generated_strategy(spec.name, str(generated_path))

            if strategy_class is None and generate_code != "y":
                from strategies import BBandStrategy, MACrossoverStrategy, MultiTimeframeBBandStrategy
                
                # 根據策略類型選擇現有策略
                if (
                    "bband" in normalized_indicators
                    and spec.parameters
                    and "higher_timeframe" in spec.parameters
                    and "entry_timeframe" in spec.parameters
                ):
                    strategy_class = MultiTimeframeBBandStrategy
                elif "bband" in normalized_indicators:
                    strategy_class = BBandStrategy
                else:
                    strategy_class = MACrossoverStrategy
            
            # 如果已由 workflow 執行完整回測，直接進入後續選項
            if strategy_class is None:
                print("   ❌ 沒有可執行的策略類別，停止本次執行。")
                return

            if self.current_report and self.current_result is not None and generate_code == "y":
                backtest_result = self.current_result
                from metrics import calculate_metrics
                metrics = calculate_metrics(backtest_result)
                evaluation = self.evaluator.evaluate(backtest_result, metrics)
            else:
                # 執行回測 - 直接使用 engine
                from backtest.engine import BacktestEngine
                
                # 創建策略
                strategy = self._instantiate_strategy(strategy_class, spec.parameters)
                self._last_strategy_class = strategy_class
                
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
                
                from reports import generate_backtest_report

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
                self._run_optimization(
                    spec,
                    price_df,
                    data_path,
                    self._last_strategy_class or strategy_class,
                )
            
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
    args = parse_args()
    developer = ConversationalStrategyDeveloper(
        model=args.model,
        temperature=args.temperature,
        engineer_model=args.engineer_model,
        evaluator_model=args.evaluator_model,
        reporter_model=args.reporter_model,
    )
    developer.run_interactive()


def parse_args():
    """解析命令列參數。"""
    parser = argparse.ArgumentParser(description="對話式策略開發助手")
    parser.add_argument(
        "--model",
        default=os.environ.get("CONVERSATION_MODEL", "gemini-3-flash-preview"),
        help="對話 agent 使用的模型，可用 CONVERSATION_MODEL 覆蓋",
    )
    parser.add_argument(
        "--engineer-model",
        default=os.environ.get("ENGINEER_MODEL"),
        help="Engineer Agent 使用的模型，可用 ENGINEER_MODEL 覆蓋",
    )
    parser.add_argument(
        "--evaluator-model",
        default=os.environ.get("EVALUATOR_MODEL"),
        help="Strategy Evaluator 使用的模型，可用 EVALUATOR_MODEL 覆蓋",
    )
    parser.add_argument(
        "--reporter-model",
        default=os.environ.get("REPORTER_MODEL"),
        help="Reporter Agent 使用的模型，可用 REPORTER_MODEL 覆蓋",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=float(os.environ.get("CONVERSATION_TEMPERATURE", "0.7")),
        help="對話 agent temperature，可用 CONVERSATION_TEMPERATURE 覆蓋",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
