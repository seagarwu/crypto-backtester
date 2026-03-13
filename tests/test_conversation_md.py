"""測試 ConversationalStrategyDeveloper 的策略發想 MD 管理功能"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# 確保可以匯入模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.conversation import ConversationalStrategyDeveloper
from agents.strategy_developer_agent import StrategySpec


class TestStrategyMDManagement:
    """測試策略發想 MD 管理功能"""
    
    @pytest.fixture
    def temp_md_dir(self):
        """創建臨時 MD 目錄"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def conversation(self, temp_md_dir):
        """創建 ConversationalStrategyDeveloper 實例（使用 mock LLM）"""
        conv = ConversationalStrategyDeveloper()
        conv.md_dir = temp_md_dir
        conv._llm = MagicMock()
        return conv
    
    def test_create_strategy_md(self, conversation, temp_md_dir):
        """測試創建新的策略發想 MD"""
        filename = conversation._create_strategy_md("BTCUSDT_軌道策略")
        
        assert filename.exists()
        content = filename.read_text()
        assert "# BTCUSDT_軌道策略" in content
        assert "## 討論歷史" in content
        assert "## 策略規格" in content
        
        # 檢查 current_md_path
        assert conversation.current_md_path == filename
    
    def test_update_strategy_md_with_conversation(self, conversation, temp_md_dir):
        """測試更新 MD 中的討論歷史"""
        # 先創建 MD
        conversation._create_strategy_md("TestStrategy")
        
        # 更新討論歷史
        conversation._update_strategy_md(
            user_input="我想開發一個軌道策略",
            assistant_response="好的，請問你的進場條件是什麼？"
        )
        
        content = conversation.current_md_path.read_text()
        assert "我想開發一個軌道策略" in content
        assert "好的，請問你的進場條件是什麼？" in content
    
    def test_update_strategy_md_with_spec(self, conversation, temp_md_dir):
        """測試更新 MD 中的策略規格"""
        # 先創建 MD
        conversation._create_strategy_md("TestStrategy")
        
        # 創建 StrategySpec
        spec = StrategySpec(
            name="TestStrategy",
            description="測試策略",
            indicators=["MA_20", "BBAND_20"],
            entry_rules="價格觸及下軌買入",
            exit_rules="價格觸及上軌賣出",
            parameters={"period": 20, "std": 2.0},
            timeframe="15m"
        )
        
        # 更新策略規格
        conversation._update_strategy_md(spec=spec)
        
        content = conversation.current_md_path.read_text()
        assert "MA_20" in content
        assert "BBAND_20" in content
        assert "價格觸及下軌買入" in content
    
    def test_update_strategy_md_with_generated_file(self, conversation, temp_md_dir):
        """測試更新 MD 中的生成檔案"""
        # 先創建 MD
        conversation._create_strategy_md("TestStrategy")
        
        # 更新生成檔案
        conversation._update_strategy_md(generated_file="/path/to/strategy.py")
        
        content = conversation.current_md_path.read_text()
        assert "/path/to/strategy.py" in content
        assert "## 生成檔案" in content
    
    def test_parse_md_to_spec(self, conversation, temp_md_dir):
        """測試從 MD 解析 StrategySpec"""
        # 先創建 MD 並填入內容
        conversation._create_strategy_md("TestStrategy")
        
        md_content = """# TestStrategy

## 策略規格
- 名稱: TestStrategy
- 描述: 這是一個測試策略
- 指標: [MA_20, BBAND_20]
- 進場規則: 價格觸及下軌買入
- 出場規則: 價格觸及上軌賣出
- 參數: {'period': 20, 'std': 2.0}
- 時間框架: 15m
"""
        conversation.current_md_path.write_text(md_content)
        
        # 解析
        spec = conversation._parse_md_to_spec(md_content)
        
        assert spec.name == "TestStrategy"
        assert spec.description == "這是一個測試策略"
        assert "MA_20" in spec.indicators
        assert "BBAND_20" in spec.indicators
        assert spec.entry_rules == "價格觸及下軌買入"
        assert spec.exit_rules == "價格觸及上軌賣出"
        assert spec.parameters == {"period": 20, "std": 2.0}
        assert spec.timeframe == "15m"
    
    def test_load_strategy_md_no_files(self, conversation, temp_md_dir):
        """測試載入不存在的 MD"""
        content, spec = conversation._load_strategy_md()
        assert content is None
        assert spec is None
    
    def test_load_strategy_md_with_files(self, conversation, temp_md_dir):
        """測試載入已存在的 MD"""
        # 先創建幾個 MD
        conversation._create_strategy_md("Strategy1")
        conversation._create_strategy_md("Strategy2")
        
        # Mock input 選擇第二個
        with patch('builtins.input', return_value='2'):
            content, spec = conversation._load_strategy_md()
        
        assert content is not None
        assert "Strategy2" in content
    
    def test_update_without_md_path(self, conversation):
        """測試沒有 MD 路徑時不更新"""
        conversation.current_md_path = None
        
        # 不應該拋出異常
        conversation._update_strategy_md(user_input="test")
        
        # 確認沒有創建文件
        assert list(conversation.md_dir.glob("*.md")) == []


class TestMDContextPassing:
    """測試 MD 上下文傳遞給 Engineer Agent"""
    
    def test_generate_strategy_code_accepts_md_context(self):
        """測試 generate_strategy_code 接受 md_context 參數"""
        from agents.strategy_developer_agent import StrategyDeveloperAgent
        import inspect
        
        sig = inspect.signature(StrategyDeveloperAgent.generate_strategy_code)
        params = list(sig.parameters.keys())
        
        assert 'md_context' in params


class TestGeneratedStrategyCodeHandling:
    """測試生成策略代碼的抽取、保存與載入。"""

    @pytest.fixture
    def conversation(self, tmp_path):
        conv = ConversationalStrategyDeveloper()
        conv.md_dir = tmp_path / "ideas"
        conv._llm = MagicMock()
        return conv

    def test_extract_python_code_skips_non_code_preamble(self, conversation):
        content = """
這是策略說明：
- 使用布林通道

from strategies.base import BaseStrategy, SignalType
import pandas as pd

class DemoStrategy(BaseStrategy):
    @property
    def required_indicators(self) -> list:
        return []

    def calculate_signals(self, data: pd.DataFrame, indicators: dict) -> dict:
        return {"signal": 0, "strength": 0.5}

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        return pd.Series([SignalType.HOLD] * len(data), index=data.index)
"""
        extracted = conversation._extract_python_code(content)

        assert extracted.startswith("from strategies.base")
        assert "class DemoStrategy" in extracted

    def test_extract_python_code_stops_before_trailing_narrative(self, conversation):
        content = """
from strategies.base import BaseStrategy, SignalType
import pandas as pd

class DemoStrategy(BaseStrategy):
    @property
    def required_indicators(self) -> list:
        return []

    def calculate_signals(self, data: pd.DataFrame, indicators: dict) -> dict:
        return {"signal": SignalType.HOLD, "strength": 0.5}

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        return pd.Series([SignalType.HOLD] * len(data), index=data.index)

1. 這裡是額外說明，不是程式碼
2. 也不應該被保留下來
"""
        extracted = conversation._extract_python_code(content)

        assert "class DemoStrategy" in extracted
        assert "這裡是額外說明" not in extracted

    def test_save_strategy_code_returns_none_for_invalid_content(self, conversation):
        saved = conversation._save_strategy_code(
            "BrokenStrategy",
            "({'open': 'first', 'high': 'max'})`.\n* Calculate BBands on df_4h.",
        )

        assert saved is None

    def test_load_generated_strategy_returns_none_for_invalid_file(self, conversation, tmp_path):
        bad_file = tmp_path / "broken_strategy.py"
        bad_file.write_text('"""bad"""\nnot valid python ???\n', encoding="utf-8")

        loaded = conversation._load_generated_strategy("BrokenStrategy", str(bad_file))

        assert loaded is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
