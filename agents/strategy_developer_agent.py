#!/usr/bin/env python3
"""
Strategy Developer Agent - 策略研發 Agent

職責：
- 根據市場狀況分析，開發新的交易策略
- 結合現有策略經驗，優化參數
- 生成策略規格說明書
"""

import os
import sys
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
import re
import ast

# 確保可以匯入模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 直接從 core 匯入
from core.llm_manager import get_llm
from agents.agent_prompting import build_agent_context

# Agent 角色定義（避免循環導入）
from enum import Enum
from dataclasses import dataclass

class AgentRole(Enum):
    """Agent 角色定義"""
    MARKET_MONITOR = "market_monitor"
    RISK_MANAGER = "risk_manager"
    STRATEGY_DEVELOPER = "strategy_dev"
    BACKTESTER = "backtester"
    ENGINEER = "engineer"
    REPORTER = "reporter"

@dataclass
class AgentConfig:
    """Agent 配置"""
    role: AgentRole
    model: str = "gemini-2.5-pro"
    temperature: float = 0.7
    max_tokens: int = 2000
    system_prompt: str = ""


# Agent Prompt 模板
AGENT_PROMPTS = {
    AgentRole.STRATEGY_DEVELOPER: """你是一個量化策略開發專家。

你的職責：
- 根據市場狀況設計交易策略
- 優化策略參數
- 識別新的交易機會

請提供：
1. 策略建議
2. 參數優化建議
3. 風險調整後的預期收益""",
    
    AgentRole.BACKTESTER: """你是一個回測專家。

你的職責：
- 測試交易策略的歷史表現
- 計算關鍵指標（Sharpe, Drawdown, Win Rate）
- 提供改進建議""",
    
    AgentRole.REPORTER: """你是一個投資組合經理助手。

你的職責：
- 彙總各Agent的分析結果
- 生成人類可讀的報告
- 突出關鍵決策點""",
}


logger = logging.getLogger(__name__)


@dataclass
class StrategySpec:
    """策略規格"""
    name: str
    description: str
    indicators: List[str] = field(default_factory=list)
    entry_rules: str = ""
    exit_rules: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    timeframe: str = "1h"
    risk_level: str = "medium"


@dataclass
class EngineerCodeResult:
    """Engineer Agent 的結構化代碼輸出。"""
    code: str
    summary: str = ""
    assumptions: List[str] = field(default_factory=list)
    raw_response: str = ""


class StrategyDeveloperAgent:
    """
    策略研發 Agent
    
    使用 LLM 根據市場環境和現有策略經驗，開發新的交易策略
    """
    
    def __init__(
        self,
        model: str = "gemini-2.5-pro",
        temperature: float = 0.8,
    ):
        self.model = model
        self.temperature = temperature
        self.llm = None
        
        # 系統 Prompt
        self.system_prompt = AGENT_PROMPTS.get(
            AgentRole.STRATEGY_DEVELOPER,
            """你是一個量化策略開發專家。
            
你的職責：
- 根據市場狀況設計交易策略
- 優化策略參數
- 識別新的交易機會

請提供：
1. 策略建議
2. 參數優化建議
3. 風險調整後的預期收益"""
        )
    
    def _get_llm(self):
        """懒加载 LLM"""
        if self.llm is None:
            # 使用便捷函数，直接传递模型参数
            self.llm = get_llm(
                model_name=self.model,
                temperature=self.temperature,
                max_tokens=2000,
            )
        return self.llm
    
    def develop_strategy(
        self,
        market_analysis: str,
        existing_strategies: List[str] = None,
        target_metrics: Dict[str, float] = None,
    ) -> StrategySpec:
        """
        開發新策略
        
        Args:
            market_analysis: 市場分析結果
            existing_strategies: 現有策略列表
            target_metrics: 目標指標 (如 Sharpe > 1.5)
            
        Returns:
            StrategySpec: 策略規格
        """
        llm = self._get_llm()
        
        # 構建 prompt
        strategies_text = ", ".join(existing_strategies) if existing_strategies else "無"
        metrics_text = ""
        if target_metrics:
            metrics_text = "\n目標指標：" + ", ".join([
                f"{k} > {v}" for k, v in target_metrics.items()
            ])
        
        prompt = f"""
請根據以下資訊，開發一個新的交易策略：

## 市場分析
{market_analysis}

## 現有策略
{strategies_text}
{metrics_text}

## 輸出格式 (JSON)
請嚴格以下格式輸出，不要有額外文字：
{{
    "name": "策略名稱",
    "description": "策略簡短描述",
    "indicators": ["MA", "RSI", "MACD"],
    "entry_rules": "進場規則描述",
    "exit_rules": "出場規則描述",
    "parameters": {{
        "param1": value1,
        "param2": value2
    }},
    "timeframe": "1h",
    "risk_level": "low/medium/high"
}}

請確保輸出的策略是創新的，且與現有策略有所不同。
"""
        
        try:
            response = llm.invoke(prompt)
            content = response.content
            
            # 解析 JSON
            # 嘗試找到 JSON 區塊
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            data = json.loads(content.strip())
            
            return StrategySpec(
                name=data.get("name", "New Strategy"),
                description=data.get("description", ""),
                indicators=data.get("indicators", []),
                entry_rules=data.get("entry_rules", ""),
                exit_rules=data.get("exit_rules", ""),
                parameters=data.get("parameters", {}),
                timeframe=data.get("timeframe", "1h"),
                risk_level=data.get("risk_level", "medium"),
            )
            
        except Exception as e:
            logger.error(f"策略開發失敗: {e}")
            # 返回默認策略
            return StrategySpec(
                name="Fallback Strategy",
                description="基於簡單均線的策略",
                indicators=["MA(20)", "MA(50)"],
                entry_rules="短均線上穿長均線買入",
                exit_rules="短均線下穿長均線賣出",
                parameters={"fast_ma": 20, "slow_ma": 50},
                timeframe="1h",
                risk_level="medium",
            )
    
    def optimize_strategy(
        self,
        strategy: StrategySpec,
        backtest_results: Dict[str, Any],
    ) -> StrategySpec:
        """
        根據回測結果優化策略
        
        Args:
            strategy: 現有策略
            backtest_results: 回測結果
            
        Returns:
            StrategySpec: 優化後的策略
        """
        llm = self._get_llm()
        normalized_results = self._normalize_backtest_results(backtest_results)
        
        prompt = f"""
請根據以下回測結果，優化策略參數：

## 原始策略
- 名稱: {strategy.name}
- 描述: {strategy.description}
- 指標: {', '.join(strategy.indicators)}
- 參數: {json.dumps(strategy.parameters)}
- 進場規則: {strategy.entry_rules}
- 出場規則: {strategy.exit_rules}

## 回測結果
- 總收益率: {normalized_results.get('total_return', 0):.2f}%
- Sharpe Ratio: {normalized_results.get('sharpe_ratio', 0):.2f}
- 最大回撤: {normalized_results.get('max_drawdown', 0):.2f}%
- 勝率: {normalized_results.get('win_rate', 0):.2f}%
- 交易次數: {normalized_results.get('total_trades', 0)}

## 問題診斷
{self._diagnose_results(normalized_results)}

## 輸出格式 (JSON)
請嚴格以下格式輸出：
{{
    "name": "優化後策略名稱",
    "description": "優化說明",
    "indicators": ["保持或修改指標"],
    "entry_rules": "修改後的進場規則",
    "exit_rules": "修改後的出不規則",
    "parameters": {{
        "param1": new_value1,
        "param2": new_value2
    }},
    "timeframe": "保持或修改",
    "risk_level": "low/medium/high"
}}
"""
        
        try:
            response = llm.invoke(prompt)
            content = response.content
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            data = json.loads(content.strip())
            
            return StrategySpec(
                name=data.get("name", strategy.name + "_optimized"),
                description=data.get("description", strategy.description),
                indicators=data.get("indicators", strategy.indicators),
                entry_rules=data.get("entry_rules", strategy.entry_rules),
                exit_rules=data.get("exit_rules", strategy.exit_rules),
                parameters=data.get("parameters", strategy.parameters),
                timeframe=data.get("timeframe", strategy.timeframe),
                risk_level=data.get("risk_level", strategy.risk_level),
            )
            
        except Exception as e:
            logger.error(f"策略優化失敗: {e}")
            return strategy

    def _normalize_backtest_results(self, results: Any) -> Dict[str, Any]:
        if isinstance(results, dict):
            return results
        return {
            "total_return": getattr(results, "total_return", 0),
            "sharpe_ratio": getattr(results, "sharpe_ratio", 0),
            "max_drawdown": getattr(results, "max_drawdown", 0),
            "win_rate": getattr(results, "win_rate", 0),
            "total_trades": getattr(results, "total_trades", 0),
            "profit_factor": getattr(results, "profit_factor", 0),
        }
    
    def _diagnose_results(self, results: Dict[str, Any]) -> str:
        """診斷回測結果"""
        issues = []
        
        sharpe = results.get("sharpe_ratio", 0)
        if sharpe < 1.0:
            issues.append("- Sharpe Ratio 低於 1.0，風險調整收益不佳")
        elif sharpe > 2.0:
            issues.append(f"- Sharpe Ratio 很高 ({sharpe:.2f})，可能過擬合")
        
        drawdown = results.get("max_drawdown", 0)
        if drawdown > 30:
            issues.append(f"- 最大回撤過大 ({drawdown:.1f}%)")
        
        win_rate = results.get("win_rate", 0)
        if win_rate < 40:
            issues.append(f"- 勝率偏低 ({win_rate:.1f}%)")
        
        trades = results.get("total_trades", 0)
        if trades < 10:
            issues.append(f"- 交易次數過少 ({trades})，樣本不足")
        
        if not issues:
            return "無明顯問題"
        
        return "\n".join(issues)
    
    def generate_strategy_code(self, spec: StrategySpec, md_context: str = None) -> str:
        """
        生成策略代碼 (Engineer Agent)
        
        Args:
            spec: 策略規格
            md_context: 策略發想 MD 的內容（可選，用於提供更多上下文）
            
        Returns:
            str: Python 代碼
        """
        code, _ = self._generate_strategy_code_with_raw(spec, md_context=md_context)
        return code

    def _generate_strategy_code_with_raw(
        self,
        spec: StrategySpec,
        md_context: str = None,
    ) -> tuple[str, str]:
        """生成策略代碼並保留原始模型輸出，便於 fallback debug。"""
        llm = self._get_llm()
        context = self._extract_strategy_context(md_context)
        agent_context = build_agent_context("engineer_agent")
        repo_contract = self._repo_contract_prompt_block()
        skeleton = self._repo_native_class_skeleton(spec)

        prompt = f"""你是一個專業的量化交易策略工程師。

任務：根據下列策略規格，直接輸出完整可執行的 Python 原始碼。

工程規則與工具上下文：
{agent_context or '無'}

Repo 契約：
{repo_contract}

限制：
1. 只輸出 Python 原始碼。
2. 不要輸出 markdown。
3. 不要輸出說明文字。
4. 第一行必須是 import 或 from。
5. 程式碼中必須包含一個繼承 BaseStrategy 的 class。
6. 必須實作 generate_signals；如有參數，請在 __init__ 定義並用 get_params() 回傳。
7. required_indicators 應在 __init__ 設定或以 @property 暴露。
8. generate_signals 必須回傳 pandas.DataFrame，至少包含 datetime 與 signal 欄位。
9. 不要使用未定義的 self.config、self.params 或其他框架中不存在的屬性。
10. calculate_signals 不是框架要求，除非真的需要，不要額外發明。
8. 只允許使用 Python 標準庫、pandas、numpy 與 repo 內模組；禁止使用 pandas_ta、ta-lib、backtrader、vectorbt 或其他額外第三方套件。

策略規格：
- 名稱: {spec.name}
- 描述: {spec.description}
- 指標: {', '.join(spec.indicators)}
- 進場規則: {spec.entry_rules or '價格觸及支撐線進場'}
- 出場規則: {spec.exit_rules or '價格觸及壓力線出場'}
- 參數: {spec.parameters}
- 時間框架: {spec.timeframe}
- 風險等級: {spec.risk_level}

補充上下文：
{context or '無'}

必要程式骨架：
{skeleton}
"""

        try:
            response = llm.invoke(prompt)
            raw = response.content if hasattr(response, "content") else str(response)
            code = self._clean_code_block(raw)
            return code.strip(), raw
        except Exception as e:
            logger.error(f"代碼生成失敗: {e}")
            return "", ""

    def generate_strategy_code_structured(
        self,
        spec: StrategySpec,
        md_context: str = None,
        feedback: Optional[Dict[str, Any]] = None,
        previous_code: str = "",
    ) -> EngineerCodeResult:
        """生成結構化代碼輸出，便於後續驗證與迭代。"""
        llm = self._get_llm()
        context = self._extract_strategy_context(md_context)
        feedback_text = json.dumps(feedback or {}, ensure_ascii=False, indent=2)
        prompt = self._build_structured_code_prompt(
            spec=spec,
            context=context,
            feedback_text=feedback_text,
            previous_code=previous_code,
        )

        try:
            response = llm.invoke(prompt)
            raw = response.content if hasattr(response, "content") else str(response)
            data = self._parse_structured_response(raw)
            code = self._clean_code_block(str(data.get("code", "")))
            return EngineerCodeResult(
                code=code,
                summary=str(data.get("summary", "")),
                assumptions=[str(item) for item in data.get("assumptions", [])],
                raw_response=raw,
            )
        except Exception as e:
            logger.error(f"結構化代碼生成失敗: {e}")
            fallback_code, fallback_raw = self._generate_strategy_code_with_raw(
                spec,
                md_context=md_context,
            )
            return EngineerCodeResult(
                code=fallback_code,
                summary="Fallback to legacy code generation",
                assumptions=[],
                raw_response=self._merge_raw_responses(raw if 'raw' in locals() else "", fallback_raw),
            )

    def revise_strategy_code(
        self,
        spec: StrategySpec,
        feedback: Dict[str, Any],
        previous_code: str,
        md_context: str = None,
    ) -> EngineerCodeResult:
        """根據上一輪 feedback 修正策略程式碼。"""
        llm = self._get_llm()
        context = self._extract_strategy_context(md_context)
        feedback_text = json.dumps(feedback or {}, ensure_ascii=False, indent=2)
        prompt = self._build_revision_prompt(
            spec=spec,
            context=context,
            feedback_text=feedback_text,
            previous_code=previous_code,
        )

        try:
            response = llm.invoke(prompt)
            raw = response.content if hasattr(response, "content") else str(response)
            data = self._parse_structured_response(raw)
            code = self._clean_code_block(str(data.get("code", "")))
            return EngineerCodeResult(
                code=code,
                summary=str(data.get("summary", "")),
                assumptions=[str(item) for item in data.get("assumptions", [])],
                raw_response=raw,
            )
        except Exception as e:
            logger.error(f"修正代碼生成失敗: {e}")
            fallback_code, fallback_raw = self._generate_strategy_code_with_raw(
                spec,
                md_context=md_context,
            )
            return EngineerCodeResult(
                code=fallback_code,
                summary="Fallback to legacy regeneration after revision failure",
                assumptions=[],
                raw_response=self._merge_raw_responses(raw if 'raw' in locals() else "", fallback_raw),
            )

    def _build_structured_code_prompt(
        self,
        spec: StrategySpec,
        context: str,
        feedback_text: str,
        previous_code: str,
    ) -> str:
        """建立首輪或全量重生成 prompt。"""
        agent_context = build_agent_context("engineer_agent")
        repo_contract = self._repo_contract_prompt_block()
        skeleton = self._repo_native_class_skeleton(spec)
        return f"""你是一個專業的量化交易策略工程師。

請根據策略規格、前一輪代碼與 feedback，輸出嚴格的三個區塊。
不要輸出 markdown，不要輸出額外說明，不要輸出 JSON。

工程規則與工具上下文：
{agent_context or '無'}

Repo 契約：
{repo_contract}

輸出格式必須完全如下：
<SUMMARY>
本輪修改摘要
</SUMMARY>
<ASSUMPTIONS>
- 假設1
- 假設2
</ASSUMPTIONS>
<CODE>
完整 Python 原始碼
</CODE>

要求：
1. code 必須是完整可執行的 Python。
2. code 第一行必須是 import 或 from。
3. 必須包含繼承 BaseStrategy 的 class。
4. BaseStrategy 唯一強制抽象方法是 generate_signals；不要把 calculate_signals 當成必需方法。
5. 如果策略有參數，請在 __init__ 定義，並在 get_params() 回傳。
6. required_indicators 應在 __init__ 設定或以 @property 暴露。
7. generate_signals 必須回傳 DataFrame，至少包含 datetime 與 signal 欄位。
8. 不要使用未定義的 self.config、self.params 或其他 repo 中不存在的屬性。
9. 不要省略任何 method，不要用 ...、TODO、佔位文字。
10. 禁止匯入 pandas_ta、ta-lib、backtrader、vectorbt 或其他 repo 未內建的第三方交易函式庫。
11. 如果你不確定某個 repo framework 方法是否存在，就不要發明；優先遵守上面的 Repo 契約。

在輸出前，請自行檢查但不要輸出檢查結果：
- class 是否繼承 BaseStrategy
- 是否呼叫 super().__init__(...)
- 是否沒有 self.config / self.params
- generate_signals 是否完整且回傳 DataFrame
- 程式碼是否能被 Python 解析

策略規格：
- 名稱: {spec.name}
- 描述: {spec.description}
- 指標: {', '.join(spec.indicators)}
- 進場規則: {spec.entry_rules}
- 出場規則: {spec.exit_rules}
- 參數: {spec.parameters}
- 時間框架: {spec.timeframe}
- 風險等級: {spec.risk_level}

補充上下文：
{context or '無'}

上一輪代碼：
{previous_code or '無'}

上一輪 feedback：
{feedback_text}

可直接參考的最小骨架：
{skeleton}
"""

    def _build_revision_prompt(
        self,
        spec: StrategySpec,
        context: str,
        feedback_text: str,
        previous_code: str,
    ) -> str:
        """建立修補導向 prompt，避免每輪重寫整份 class。"""
        agent_context = build_agent_context("engineer_agent")
        repo_contract = self._repo_contract_prompt_block()
        skeleton = self._repo_native_class_skeleton(spec)
        return f"""你是一個 Python 策略修復工程師。

你的任務不是重寫整份策略，而是基於現有代碼做最小必要修正，讓它通過驗證。
請保留現有 class 名稱、參數名稱與主要策略邏輯，只修復 feedback 指出的問題。

工程規則與工具上下文：
{agent_context or '無'}

Repo 契約：
{repo_contract}

不要輸出 markdown，不要輸出額外說明，不要輸出 JSON。
輸出格式必須完全如下：
<SUMMARY>
本輪修復摘要
</SUMMARY>
<ASSUMPTIONS>
- 假設1
</ASSUMPTIONS>
<CODE>
完整修正後的 Python 原始碼
</CODE>

硬性要求：
1. 必須保留同一個 BaseStrategy 子類名稱：{spec.name}
2. 必須提供完整 __init__，並呼叫 super().__init__(...)
3. BaseStrategy 唯一強制抽象方法是 generate_signals；不要把 calculate_signals 當成框架要求
4. 如果策略有參數，請在 __init__ 定義，並在 get_params() 回傳
5. required_indicators 應在 __init__ 設定或以 @property 暴露
6. 不要使用未定義的 self.config、self.params
4. 如果 feedback 提到 syntax error，先修語法，不要重構
5. 如果 feedback 提到缺少 generate_signals，直接補上完整實作
6. 不要輸出半截 method，不要輸出 ...、TODO、註解佔位
7. generate_signals 必須回傳 DataFrame，至少包含 datetime 與 signal 欄位
8. 禁止匯入 pandas_ta、ta-lib、backtrader、vectorbt 或其他 repo 未內建的第三方交易函式庫
9. 如果上一輪使用了 repo 中不存在的屬性或框架方法，直接移除，改成 repo-native 寫法

在輸出前，請自行檢查但不要輸出檢查結果：
- class 名稱是否保持不變
- super().__init__(...) 是否存在
- generate_signals 是否完整
- 是否沒有 self.config / self.params
- 程式碼是否能被 Python 解析

策略規格：
- 名稱: {spec.name}
- 描述: {spec.description}
- 指標: {', '.join(spec.indicators)}
- 參數: {spec.parameters}

補充上下文：
{context or '無'}

上一輪完整代碼：
{previous_code or '無'}

必須修復的 feedback：
{feedback_text}

如果需要，退回這個最小 repo-native 骨架再補策略邏輯：
{skeleton}
"""

    def _repo_contract_prompt_block(self) -> str:
        """回傳與本 repo BaseStrategy 對齊的硬性契約。"""
        return """- BaseStrategy 定義在 strategies/base.py。
- BaseStrategy 的 __init__ 只有 name 參數；正確寫法是 super().__init__(name=...)
- BaseStrategy 唯一強制抽象方法是 generate_signals(self, data: pd.DataFrame) -> pd.DataFrame
- required_indicators 不是抽象方法；可在 __init__ 設為 list，或用 @property 回傳 list
- get_params() 是可選的；只有策略有可調參數時才需要覆寫
- prepare_data() 是可選的前處理 hook
- generate_signals 回傳的 DataFrame 必須至少包含 signal 欄位；若原始資料有 datetime，應保留；若沒有，請建立 datetime 欄位
- SignalType 定義在 strategies/base.py，使用 SignalType.BUY / HOLD / SELL
- 不要依賴 repo 不存在的框架欄位，例如 self.config、self.params
- calculate_signals 不是框架要求；除非實作真的需要，否則不要新增
"""

    def _repo_native_class_skeleton(self, spec: StrategySpec) -> str:
        """提供最小可用、與本 repo 契約對齊的骨架。"""
        class_name = self._sanitize_strategy_class_name(spec.name)
        return f"""from strategies.base import BaseStrategy, SignalType
import pandas as pd

class {class_name}(BaseStrategy):
    def __init__(self, name: str | None = None):
        super().__init__(name=name or {spec.name!r})
        self.required_indicators = []

    def get_params(self) -> dict:
        return {{}}

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        if \"datetime\" not in df.columns:
            df[\"datetime\"] = df.index
        df[\"signal\"] = SignalType.HOLD
        return df
"""

    def _sanitize_strategy_class_name(self, name: str) -> str:
        """將策略名稱轉成穩定的 Python class 名稱。"""
        tokens = re.findall(r"[A-Za-z0-9]+", name or "")
        if not tokens:
            return "GeneratedStrategy"
        normalized = "".join(token.capitalize() for token in tokens)
        if not normalized.endswith("Strategy"):
            normalized += "Strategy"
        return normalized

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """從模型回應中提取 JSON。"""
        text = content.strip()
        if text.startswith("```json"):
            text = text[len("```json"):]
            if text.endswith("```"):
                text = text[:-3]
        elif text.startswith("```"):
            first_newline = text.find("\n")
            text = text[first_newline + 1:] if first_newline != -1 else text[3:]
            if text.endswith("```"):
                text = text[:-3]
        return json.loads(text.strip())

    def _parse_structured_response(self, content: str) -> Dict[str, Any]:
        """從區塊標記回應中提取 summary / assumptions / code。"""
        summary_match = re.search(r"<SUMMARY>\s*(.*?)\s*</SUMMARY>", content, flags=re.DOTALL)
        assumptions_match = re.search(r"<ASSUMPTIONS>\s*(.*?)\s*</ASSUMPTIONS>", content, flags=re.DOTALL)
        code_match = re.search(r"<CODE>\s*(.*?)\s*</CODE>", content, flags=re.DOTALL)

        extracted_code = ""
        if code_match:
            extracted_code = code_match.group(1).strip()
        else:
            extracted_code = self._extract_python_code(content)
            if not extracted_code:
                raise ValueError("Missing <CODE> block in structured response")

        assumptions = []
        if assumptions_match:
            for line in assumptions_match.group(1).splitlines():
                line = line.strip()
                if not line:
                    continue
                assumptions.append(line.lstrip("- ").strip())

        return {
            "summary": summary_match.group(1).strip() if summary_match else "",
            "assumptions": assumptions,
            "code": extracted_code,
        }

    def _clean_code_block(self, code: str) -> str:
        """移除 markdown 與敘述雜訊，盡量保留可解析的 Python。"""
        code = code.strip()
        if code.startswith("```python"):
            code = code[10:]
        elif code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
        code = code.strip()

        extracted = self._extract_python_code(code)
        return extracted or code

    def _merge_raw_responses(self, primary_raw: str, fallback_raw: str) -> str:
        """保留 structured / fallback 兩段原始輸出，方便事後比對。"""
        parts = []
        if primary_raw:
            parts.append("[structured_attempt]\n" + primary_raw.strip())
        if fallback_raw:
            parts.append("[legacy_fallback]\n" + fallback_raw.strip())
        return "\n\n".join(parts)

    def _extract_python_code(self, content: str) -> str:
        """從混合文字中提取最可能的 Python 程式碼。"""
        if not content:
            return ""

        candidates: List[str] = []

        fenced_blocks = re.findall(r"```(?:python)?\s*(.*?)```", content, flags=re.DOTALL)
        candidates.extend(block.strip() for block in fenced_blocks if block.strip())

        tag_match = re.search(r"<CODE>\s*(.*?)\s*(?:</CODE>|$)", content, flags=re.DOTALL)
        if tag_match:
            candidates.append(tag_match.group(1).strip())

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

        stripped = content.strip()
        if stripped and re.search(r"(^|\n)\s*(from |import |class |def )", stripped):
            candidates.append(stripped)

        seen = set()
        for candidate in candidates:
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            trimmed = self._trim_to_valid_python(candidate)
            if trimmed:
                return trimmed

        return ""

    def _collect_code_lines(self, lines: List[str]) -> List[str]:
        """從混合輸出中收集看起來像 Python 的區塊。"""
        collected: List[str] = []
        started = False

        for line in lines:
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
        """判斷一行是否更像敘述文字而不是 Python。"""
        stripped = line.strip()
        normalized = line.lstrip()

        if not stripped:
            return False

        if "HTTP Request:" in stripped:
            return True

        if stripped.startswith(("<SUMMARY>", "</SUMMARY>", "<ASSUMPTIONS>", "</ASSUMPTIONS>", "<CODE>", "</CODE>")):
            return True

        if re.match(r"^\d+\.\s", stripped):
            return True

        if re.match(r"^[-*]\s", stripped):
            return True

        if re.match(r"^[\u4e00-\u9fff]", stripped):
            return True

        if stripped.startswith(("```", "...", "*Implementation detail")):
            return True

        allowed_prefixes = (
            "from ", "import ", "class ", "def ", "@", "#",
            "if ", "elif ", "else", "for ", "while ", "try", "except", "finally",
            "with ", "return", "pass", "break", "continue", "raise", "yield", "assert",
            '"""', "'''", ")", "]", "}", ",",
        )
        if normalized.startswith(allowed_prefixes):
            return False

        if normalized.startswith((
            "self.", "signals", "signal", "result", "data", "df", "df_", "bb_",
            "position", "entry_price", "current_time", "stop_price",
        )):
            return False

        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*=", normalized):
            return False

        if line.startswith((" ", "\t")):
            return False

        return True

    def _trim_to_valid_python(self, candidate: str) -> str:
        """從候選內容尾端回退，找到可解析的 Python。"""
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

    def _extract_strategy_context(self, md_context: Optional[str]) -> str:
        """從策略 MD 中提取與生成程式碼直接相關的內容。"""
        if not md_context:
            return ""

        sections = []

        spec_match = re.search(
            r"##\s*策略規格\s*(.*?)(?:\n##\s+|\Z)",
            md_context,
            flags=re.DOTALL,
        )
        if spec_match:
            sections.append(spec_match.group(1).strip())

        if not sections:
            lines = []
            for line in md_context.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.startswith(("- 20", "20", "http", "## 生成檔案")):
                    continue
                if "HTTP Request:" in stripped or ".py" in stripped:
                    continue
                lines.append(stripped)
            sections.append("\n".join(lines[:12]))

        return "\n\n".join(section for section in sections if section).strip()


# 便捷函數
def create_strategy_developer(
    model: str = "gemini-2.5-pro",
) -> StrategyDeveloperAgent:
    """建立策略研發 Agent"""
    return StrategyDeveloperAgent(model=model)


__all__ = [
    "StrategyDeveloperAgent",
    "StrategySpec",
    "EngineerCodeResult",
    "create_strategy_developer",
]
