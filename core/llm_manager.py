"""
LLM Manager - 模型管理系統

功能：
- 統一管理多個 LLM 模型
- 根據任務類型自動選擇最佳模型
- 每個 Agent 可獨立配置模型
- 支援 OpenRouter 和 OpenAI
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import os

from langchain_openrouter import ChatOpenRouter
from langchain_openai import ChatOpenAI


class ModelProvider(Enum):
    """模型提供商"""
    OPENROUTER = "openrouter"
    OPENAI = "openai"


@dataclass
class ModelConfig:
    """模型配置"""
    name: str  # 模型名稱 (如 "minimax/minimax-chat")
    provider: ModelProvider = ModelProvider.OPENROUTER
    temperature: float = 0.7
    max_tokens: int = 2000
    description: str = ""
    strengths: List[str] = field(default_factory=list)  # 擅長領域
    weaknesses: List[str] = field(default_factory=list)  # 劣勢
    cost_tier: str = "medium"  # low, medium, high


# ==================== 預設模型 ====================

AVAILABLE_MODELS: Dict[str, ModelConfig] = {
    # MiniMax 系列 - 性價比高
    "minimax/minimax-chat": ModelConfig(
        name="minimax/minimax-chat",
        provider=ModelProvider.OPENROUTER,
        temperature=0.7,
        description="MiniMax Chat - 性價比高",
        strengths=["中文理解", "快速回應", "成本低"],
        weaknesses=["複雜推理"],
        cost_tier="low",
    ),
    
    # Claude 系列 - 擅長分析
    "anthropic/claude-3-opus": ModelConfig(
        name="anthropic/claude-3-opus",
        provider=ModelProvider.OPENROUTER,
        temperature=0.7,
        description="Claude 3 Opus - 頂級分析能力",
        strengths=["複雜推理", "長文本分析", "程式碼生成"],
        weaknesses=["成本高"],
        cost_tier="high",
    ),
    
    "anthropic/claude-3-sonnet": ModelConfig(
        name="anthropic/claude-3-sonnet",
        provider=ModelProvider.OPENROUTER,
        temperature=0.7,
        description="Claude 3 Sonnet - 平衡選擇",
        strengths=["分析", "編碼", "性價比好"],
        weaknesses=[],
        cost_tier="medium",
    ),
    
    # GPT 系列 - 通用能力強
    "openai/gpt-4-turbo": ModelConfig(
        name="openai/gpt-4-turbo",
        provider=ModelProvider.OPENROUTER,
        temperature=0.7,
        description="GPT-4 Turbo - 通用強大",
        strengths=["通用理解", "程式碼", "創意"],
        weaknesses=["成本較高"],
        cost_tier="high",
    ),
    
    "openai/gpt-3.5-turbo": ModelConfig(
        name="openai/gpt-3.5-turbo",
        provider=ModelProvider.OPENROUTER,
        temperature=0.7,
        description="GPT-3.5 Turbo - 快速便宜",
        strengths=["速度", "成本低", "日常任務"],
        weaknesses=["複雜推理"],
        cost_tier="low",
    ),
    
    # Gemini 系列 - 多模態
    "google/gemini-pro-1.5": ModelConfig(
        name="google/gemini-pro-1.5",
        provider=ModelProvider.OPENROUTER,
        temperature=0.7,
        description="Gemini Pro 1.5 - 長上下文",
        strengths=["長上下文", "多模態", "推理"],
        weaknesses=["中文優化"],
        cost_tier="medium",
    ),
    
    # Mistral - 開源強者
    "mistralai/mixtral-8x7b": ModelConfig(
        name="mistralai/mixtral-8x7b",
        provider=ModelProvider.OPENROUTER,
        temperature=0.7,
        description="Mixtral 8x7B - 開源強者",
        strengths=["開源", "成本低", "多語言"],
        weaknesses=["穩定性"],
        cost_tier="low",
    ),
    
    # 推理模型
    "openai/o1-preview": ModelConfig(
        name="openai/o1-preview",
        provider=ModelProvider.OPENROUTER,
        temperature=1.0,
        description="OpenAI O1 Preview - 推理專家",
        strengths=["複雜推理", "數學", "程式"],
        weaknesses=["速度慢", "無 Function Calling"],
        cost_tier="high",
    ),
    
    "openai/o1-mini": ModelConfig(
        name="openai/o1-mini",
        provider=ModelProvider.OPENROUTER,
        temperature=1.0,
        description="OpenAI O1 Mini - 快速推理",
        strengths=["推理速度", "程式"],
        weaknesses=["知識截止"],
        cost_tier="medium",
    ),
}


# ==================== 任務對應模型 ====================

TASK_MODEL_MAPPING = {
    # 市場分析 - 需要快速理解和數據處理
    "market_analysis": ["minimax/minimax-chat", "openai/gpt-3.5-turbo"],
    
    # 風險評估 - 需要謹慎推理
    "risk_assessment": ["anthropic/claude-3-sonnet", "openai/gpt-4-turbo"],
    
    # 策略開發 - 需要創意和技術能力
    "strategy_development": ["openai/gpt-4-turbo", "anthropic/claude-3-opus"],
    
    # 代碼生成 - 需要精確
    "code_generation": ["openai/gpt-4-turbo", "anthropic/claude-3-opus"],
    
    # 報告生成 - 需要流暢寫作
    "report_generation": ["minimax/minimax-chat", "openai/gpt-3.5-turbo"],
    
    # 複雜推理 - 需要深度思考
    "complex_reasoning": ["openai/o1-preview", "anthropic/claude-3-opus"],
    
    # 日常對話 - 快速便宜
    "general": ["minimax/minimax-chat", "openai/gpt-3.5-turbo"],
    
    # 數學/量化計算
    "mathematical": ["openai/o1-preview", "openai/o1-mini"],
}


class LLMManager:
    """
    LLM 管理器
    
    功能：
    - 統一建立 LLM 實例
    - 根據任務類型選擇模型
    - 成本控制
    """
    
    def __init__(self, default_api_key: str = None):
        """
        初始化 LLM 管理器
        
        Args:
            default_api_key: 默認 API Key
        """
        self.default_api_key = default_api_key or os.environ.get("OPENROUTER_API_KEY", "")
        
        # 實例緩存
        self._llm_cache: Dict[str, Any] = {}
        
        # 使用統計
        self._usage_stats: Dict[str, int] = {}
    
    def get_llm(
        self,
        model_name: str = None,
        temperature: float = None,
        max_tokens: int = None,
        api_key: str = None,
    ) -> Any:
        """
        獲取 LLM 實例
        
        Args:
            model_name: 模型名稱（可選）
            temperature: 溫度參數
            max_tokens: 最大 token 數
            api_key: API Key
            
        Returns:
            LLM 實例
        """
        # 默認模型
        if model_name is None:
            model_name = "minimax/minimax-chat"
        
        # 緩存 key
        cache_key = f"{model_name}_{temperature}_{max_tokens}"
        
        if cache_key in self._llm_cache:
            return self._llm_cache[cache_key]
        
        # 獲取模型配置
        model_config = AVAILABLE_MODELS.get(model_name)
        
        if model_config is None:
            # 未知的模型，使用默認配置
            model_config = ModelConfig(name=model_name)
        
        # 覆蓋參數
        temperature = temperature or model_config.temperature
        max_tokens = max_tokens or model_config.max_tokens
        
        # 建立 LLM
        if model_config.provider == ModelProvider.OPENROUTER:
            llm = ChatOpenRouter(
                model_name=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                openrouter_api_key=api_key or self.default_api_key,
            )
        elif model_config.provider == ModelProvider.OPENAI:
            llm = ChatOpenAI(
                model=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                openai_api_key=api_key,
            )
        else:
            raise ValueError(f"Unknown provider: {model_config.provider}")
        
        # 緩存
        self._llm_cache[cache_key] = llm
        
        # 統計
        self._usage_stats[model_name] = self._usage_stats.get(model_name, 0) + 1
        
        return llm
    
    def get_for_task(
        self,
        task_type: str,
        cost_control: str = "auto",  # "auto", "low", "medium", "high"
    ) -> Any:
        """
        根據任務類型獲取 LLM
        
        Args:
            task_type: 任務類型 (如 "market_analysis")
            cost_control: 成本控制 ("auto" 根據任務)
            
        Returns:
            LLM 實例
        """
        # 獲取候選模型
        candidates = TASK_MODEL_MAPPING.get(task_type, ["minimax/minimax-chat"])
        
        # 根據成本控制過濾
        if cost_control != "auto":
            filtered = []
            for model_name in candidates:
                config = AVAILABLE_MODELS.get(model_name)
                if config and config.cost_tier == cost_control:
                    filtered.append(model_name)
            if filtered:
                candidates = filtered
        
        # 選擇第一個
        model_name = candidates[0]
        
        return self.get_llm(model_name)
    
    def list_models(self) -> List[str]:
        """列出所有可用模型"""
        return list(AVAILABLE_MODELS.keys())
    
    def get_model_info(self, model_name: str) -> Optional[ModelConfig]:
        """獲取模型信息"""
        return AVAILABLE_MODELS.get(model_name)
    
    def get_usage_stats(self) -> Dict[str, int]:
        """獲取使用統計"""
        return self._usage_stats.copy()
    
    def get_recommendation(
        self,
        task_type: str,
        criteria: str = "balanced",  # "balanced", "fast", "best", "cheap"
    ) -> str:
        """
        獲取模型推薦
        
        Args:
            task_type: 任務類型
            criteria: 評估標準
            
        Returns:
            推薦的模型名稱
        """
        candidates = TASK_MODEL_MAPPING.get(task_type, ["minimax/minimax-chat"])
        
        if criteria == "fast":
            # 選擇最快的
            for m in candidates:
                config = AVAILABLE_MODELS.get(m)
                if config and config.cost_tier in ["low", "medium"]:
                    return m
        
        if criteria == "best":
            # 選擇最好的
            for m in candidates:
                config = AVAILABLE_MODELS.get(m)
                if config and config.cost_tier == "high":
                    return m
        
        if criteria == "cheap":
            # 選擇最便宜的
            for m in candidates:
                config = AVAILABLE_MODELS.get(m)
                if config and config.cost_tier == "low":
                    return m
        
        # balanced - 選擇中等
        for m in candidates:
            config = AVAILABLE_MODELS.get(m)
            if config and config.cost_tier == "medium":
                return m
        
        return candidates[0]


# ==================== 全域實例 ====================

_default_manager: Optional[LLMManager] = None


def get_llm_manager() -> LLMManager:
    """獲取默認 LLM 管理器"""
    global _default_manager
    if _default_manager is None:
        _default_manager = LLMManager()
    return _default_manager


def set_llm_manager(manager: LLMManager) -> None:
    """設置默認 LLM 管理器"""
    global _default_manager
    _default_manager = manager


# ==================== 便捷函數 ====================

def get_llm(
    model_name: str = None,
    temperature: float = None,
    max_tokens: int = None,
) -> Any:
    """便捷獲取 LLM"""
    return get_llm_manager().get_llm(model_name, temperature, max_tokens)


def get_llm_for_task(task_type: str, cost_control: str = "auto") -> Any:
    """便捷根據任務獲取 LLM"""
    return get_llm_manager().get_for_task(task_type, cost_control)


def list_available_models() -> List[str]:
    """列出所有可用模型"""
    return get_llm_manager().list_models()


def recommend_model(task_type: str, criteria: str = "balanced") -> str:
    """推薦模型"""
    return get_llm_manager().get_recommendation(task_type, criteria)
