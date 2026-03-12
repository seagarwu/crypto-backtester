"""
Unit tests for core.llm_manager module
"""

import pytest
import os
from core.llm_manager import (
    LLMManager,
    ModelConfig,
    ModelProvider,
    AVAILABLE_MODELS,
    TASK_MODEL_MAPPING,
    get_llm_manager,
    recommend_model,
)


class TestModelConfig:
    """Test ModelConfig"""
    
    def test_model_config_creation(self):
        """Test creating a ModelConfig"""
        config = ModelConfig(
            name="test/model",
            provider=ModelProvider.OPENROUTER,
            temperature=0.5,
            max_tokens=1000,
            description="Test model",
            strengths=["fast", "cheap"],
            weaknesses=["limited"],
            cost_tier="low",
        )
        
        assert config.name == "test/model"
        assert config.provider == ModelProvider.OPENROUTER
        assert config.temperature == 0.5
        assert config.cost_tier == "low"


class TestAvailableModels:
    """Test AVAILABLE_MODELS"""
    
    def test_minimax_available(self):
        """Test MiniMax model is available"""
        assert "gemini-3-flash-preview" in AVAILABLE_MODELS
        
        config = AVAILABLE_MODELS["gemini-3-flash-preview"]
        assert config.cost_tier == "medium"
    
    def test_gpt_models_available(self):
        """Test GPT models are available"""
        assert "openai/gpt-4-turbo" in AVAILABLE_MODELS
        assert "openai/gpt-3.5-turbo" in AVAILABLE_MODELS
    
    def test_claude_models_available(self):
        """Test Claude models are available"""
        assert "anthropic/claude-3-opus" in AVAILABLE_MODELS
        assert "anthropic/claude-3-sonnet" in AVAILABLE_MODELS
    
    def test_o1_models_available(self):
        """Test O1 models are available"""
        assert "openai/o1-preview" in AVAILABLE_MODELS
        assert "openai/o1-mini" in AVAILABLE_MODELS
    
    def test_all_models_have_required_fields(self):
        """Test all models have required configuration"""
        for name, config in AVAILABLE_MODELS.items():
            assert config.name == name
            assert config.provider is not None
            assert config.temperature is not None
            assert config.cost_tier in ["low", "medium", "high"]


class TestTaskModelMapping:
    """Test TASK_MODEL_MAPPING"""
    
    def test_market_analysis_mapping(self):
        """Test market_analysis task has models"""
        assert "market_analysis" in TASK_MODEL_MAPPING
        assert len(TASK_MODEL_MAPPING["market_analysis"]) > 0
    
    def test_risk_assessment_mapping(self):
        """Test risk_assessment task has models"""
        assert "risk_assessment" in TASK_MODEL_MAPPING
    
    def test_strategy_development_mapping(self):
        """Test strategy_development task has models"""
        assert "strategy_development" in TASK_MODEL_MAPPING
    
    def test_code_generation_mapping(self):
        """Test code_generation task has models"""
        assert "code_generation" in TASK_MODEL_MAPPING
    
    def test_all_mappings_have_valid_models(self):
        """Test all task mappings reference valid models"""
        for task, models in TASK_MODEL_MAPPING.items():
            for model in models:
                assert model in AVAILABLE_MODELS, f"Model {model} not in AVAILABLE_MODELS"


class TestLLMManager:
    """Test LLMManager"""
    
    def test_manager_creation(self):
        """Test creating an LLMManager"""
        manager = LLMManager()
        
        assert manager is not None
    
    def test_manager_with_api_key(self):
        """Test LLMManager with API key"""
        manager = LLMManager(default_api_key="test_key_123")
        
        assert manager.default_api_key == "test_key_123"
    
    def test_list_models(self):
        """Test listing available models"""
        manager = LLMManager()
        
        models = manager.list_models()
        
        assert len(models) > 0
        assert "gemini-3-flash-preview" in models
    
    def test_get_model_info(self):
        """Test getting model info"""
        manager = LLMManager()
        
        info = manager.get_model_info("gemini-3-flash-preview")
        
        assert info is not None
        assert info.name == "gemini-3-flash-preview"
        assert info.cost_tier == "medium"
    
    def test_get_model_info_unknown(self):
        """Test getting info for unknown model"""
        manager = LLMManager()
        
        info = manager.get_model_info("unknown/model")
        
        # Unknown model returns None (no default in current implementation)
        # This is the expected behavior
        assert info is None
    
    @pytest.mark.skipif(
        not os.environ.get("OPENROUTER_API_KEY"),
        reason="OPENROUTER_API_KEY not set"
    )
    def test_get_for_task(self):
        """Test getting LLM for task (requires API key)"""
        manager = LLMManager()
        
        llm = manager.get_for_task("market_analysis")
        
        assert llm is not None
    
    @pytest.mark.skipif(
        not os.environ.get("OPENROUTER_API_KEY"),
        reason="OPENROUTER_API_KEY not set"
    )
    def test_get_for_task_with_cost_control(self):
        """Test cost control options (requires API key)"""
        manager = LLMManager()
        
        llm = manager.get_for_task("market_analysis", cost_control="low")
        assert llm is not None
        
        llm = manager.get_for_task("market_analysis", cost_control="high")
        assert llm is not None
    
    @pytest.mark.skipif(
        not os.environ.get("OPENROUTER_API_KEY"),
        reason="OPENROUTER_API_KEY not set"
    )
    def test_usage_stats(self):
        """Test usage statistics (requires API key)"""
        manager = LLMManager()
        
        manager.get_for_task("market_analysis")
        manager.get_for_task("market_analysis")
        manager.get_for_task("risk_assessment")
        
        stats = manager.get_usage_stats()
        
        assert stats is not None


class TestRecommendModel:
    """Test recommend_model function"""
    
    def test_recommend_for_task(self):
        """Test basic recommendation"""
        model = recommend_model("market_analysis")
        
        assert model is not None
        assert model in AVAILABLE_MODELS
    
    def test_recommend_fast(self):
        """Test fast criteria"""
        model = recommend_model("market_analysis", criteria="fast")
        
        assert model is not None
    
    def test_recommend_cheap(self):
        """Test cheap criteria"""
        model = recommend_model("market_analysis", criteria="cheap")
        
        assert model is not None
    
    def test_recommend_best(self):
        """Test best criteria"""
        model = recommend_model("market_analysis", criteria="best")
        
        assert model is not None
    
    def test_recommend_balanced(self):
        """Test balanced criteria"""
        model = recommend_model("risk_assessment", criteria="balanced")
        
        assert model is not None
    
    def test_recommend_unknown_task(self):
        """Test recommendation for unknown task"""
        model = recommend_model("unknown_task")
        
        # Should fallback to default
        assert model is not None


class TestGlobalLLMManager:
    """Test global LLM manager functions"""
    
    def test_get_llm_manager(self):
        """Test get_llm_manager returns same instance"""
        manager1 = get_llm_manager()
        manager2 = get_llm_manager()
        
        assert manager1 is manager2
