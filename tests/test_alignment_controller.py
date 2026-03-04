"""
決策控制器測試

測試 DecisionController 的完整決策流程。
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from unittest.mock import Mock, patch

from alignment.controller import DecisionController
from alignment.types import Decision
from vss.types import (
    HumanJudgment,
    VSSAnalysisResult,
    MarketState,
    TrendDirection,
    PatternType,
    Momentum,
    Volatility,
)


def generate_test_data(n_bars: int = 100) -> pd.DataFrame:
    """生成測試用 K 線數據"""
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=n_bars, freq='1h')
    prices = 50000 + np.cumsum(np.random.randn(n_bars) * 100)
    
    df = pd.DataFrame({
        'open': prices * 0.99,
        'high': prices * 1.02,
        'low': prices * 0.98,
        'close': prices,
        'volume': np.random.randint(1000, 10000, n_bars),
    }, index=dates)
    
    return df


def create_market_state(
    trend: TrendDirection = TrendDirection.UP,
    confidence: float = 0.8,
) -> MarketState:
    return MarketState(
        timestamp=datetime.now(),
        trend=trend,
        trend_confidence=confidence,
        momentum=Momentum.MODERATE_BULL,
        volatility=Volatility.NORMAL,
        current_price=50000.0,
    )


def create_vss_result(
    trend: TrendDirection = TrendDirection.UP,
    confidence: float = 0.8,
    risk_level: str = "medium",
) -> VSSAnalysisResult:
    return VSSAnalysisResult(
        timestamp=datetime.now(),
        symbol="BTCUSDT",
        interval="1h",
        market_state=create_market_state(trend, confidence),
        price_change_pct=5.0,
        volume_ratio=1.2,
        risk_level=risk_level,
    )


def create_human_judgment(
    trend: TrendDirection = TrendDirection.UP,
    confidence: float = 0.75,
) -> HumanJudgment:
    return HumanJudgment(
        timestamp=datetime.now(),
        symbol="BTCUSDT",
        interval="1h",
        trend=trend,
        confidence=confidence,
        notes="Test judgment",
    )


class TestDecisionControllerInit:
    """測試控制器初始化"""
    
    def test_default_init(self):
        controller = DecisionController()
        
        assert controller.analyzer is not None
        assert controller.evaluator is not None
        assert controller.recorder is not None
    
    def test_custom_init(self):
        controller = DecisionController(
            alignment_threshold=0.8,
            confidence_threshold=0.7,
            enable_recording=False,
        )
        
        assert controller.evaluator.alignment_threshold == 0.8
        assert controller.recorder is None
    
    def test_set_execute_callback(self):
        controller = DecisionController()
        
        callback = Mock(return_value={"status": "executed"})
        controller.set_execute_callback(callback)
        
        assert controller._execute_callback == callback


class TestDecisionControllerProcess:
    """測試決策流程"""
    
    def test_process_with_dataframe(self):
        """使用 DataFrame 進行分析"""
        controller = DecisionController(enable_recording=False)
        df = generate_test_data(100)
        judgment = create_human_judgment(
            trend=TrendDirection.UP,
            confidence=0.9,
        )
        
        decision = controller.process(judgment, df)
        
        assert 'decision' in decision
        assert 'action' in decision
        assert 'reason' in decision
    
    def test_process_with_vss_result(self):
        """使用已計算的 VSS 結果"""
        controller = DecisionController(enable_recording=False)
        vss_result = create_vss_result(
            trend=TrendDirection.UP,
            confidence=0.9,
        )
        judgment = create_human_judgment(
            trend=TrendDirection.UP,
            confidence=0.9,
        )
        
        decision = controller.process(judgment, vss_result)
        
        assert decision['decision'] is True
        assert decision['action'] == Decision.APPROVE
    
    def test_process_approval_case(self):
        """測試批准決策"""
        controller = DecisionController(enable_recording=False)
        
        vss_result = create_vss_result(
            trend=TrendDirection.UP,
            confidence=0.9,
            risk_level="low",
        )
        judgment = create_human_judgment(
            trend=TrendDirection.UP,
            confidence=0.9,
        )
        
        decision = controller.process(judgment, vss_result)
        
        assert decision['decision'] is True
        assert decision['action'] == Decision.APPROVE
    
    def test_process_rejection_case(self):
        """測試拒絕決策 - 趨勢不匹配"""
        controller = DecisionController(enable_recording=False)
        
        vss_result = create_vss_result(
            trend=TrendDirection.DOWN,
            confidence=0.9,
        )
        judgment = create_human_judgment(
            trend=TrendDirection.UP,
            confidence=0.9,
        )
        
        decision = controller.process(judgment, vss_result)
        
        assert decision['decision'] is False
        assert decision['action'] == Decision.REJECT
        assert decision['trend_match'] is False
    
    def test_process_rejection_high_risk(self):
        """測試拒絕決策 - 高風險"""
        controller = DecisionController(enable_recording=False)
        
        vss_result = create_vss_result(
            trend=TrendDirection.UP,
            confidence=0.9,
            risk_level="high",
        )
        judgment = create_human_judgment(
            trend=TrendDirection.UP,
            confidence=0.9,
        )
        
        decision = controller.process(judgment, vss_result)
        
        assert decision['decision'] is False
        assert decision['action'] == Decision.REJECT


class TestDecisionControllerExecution:
    """測試交易執行"""
    
    def test_execution_callback_triggered(self):
        """測試執行回調被觸發"""
        callback = Mock(return_value={"status": "success", "price": 50000})
        controller = DecisionController(enable_recording=False)
        controller.set_execute_callback(callback)
        
        vss_result = create_vss_result(
            trend=TrendDirection.UP,
            confidence=0.9,
            risk_level="low",
        )
        judgment = create_human_judgment(
            trend=TrendDirection.UP,
            confidence=0.9,
        )
        
        decision = controller.process(judgment, vss_result)
        
        # 批准執行時應該觸發回調
        callback.assert_called_once()
        assert 'execution_result' in decision
    
    def test_execution_callback_not_triggered_on_rejection(self):
        """測試拒絕時不觸發執行回調"""
        callback = Mock(return_value={"status": "success"})
        controller = DecisionController(enable_recording=False)
        controller.set_execute_callback(callback)
        
        vss_result = create_vss_result(
            trend=TrendDirection.DOWN,
            confidence=0.9,
        )
        judgment = create_human_judgment(
            trend=TrendDirection.UP,
            confidence=0.9,
        )
        
        decision = controller.process(judgment, vss_result)
        
        # 拒絕執行時不應該觸發回調
        callback.assert_not_called()
        assert 'execution_result' not in decision
    
    def test_execution_error_handling(self):
        """測試執行錯誤處理"""
        def failing_callback(**kwargs):
            raise Exception("Execution failed")
        
        controller = DecisionController(enable_recording=False)
        controller.set_execute_callback(failing_callback)
        
        vss_result = create_vss_result(
            trend=TrendDirection.UP,
            confidence=0.9,
            risk_level="low",
        )
        judgment = create_human_judgment(
            trend=TrendDirection.UP,
            confidence=0.9,
        )
        
        decision = controller.process(judgment, vss_result)
        
        assert 'execution_error' in decision
        assert "Execution failed" in decision['execution_error']


class TestDecisionControllerSuggestions:
    """測試建議生成"""
    
    def test_approval_suggestions(self):
        """測試批准時的建議"""
        controller = DecisionController(enable_recording=False)
        
        vss_result = create_vss_result(
            trend=TrendDirection.UP,
            confidence=0.9,
        )
        judgment = create_human_judgment(
            trend=TrendDirection.UP,
            confidence=0.9,
        )
        
        decision = controller.process(judgment, vss_result)
        
        assert 'suggestion' in decision
        assert 'direction' in decision['suggestion']
        assert 'suggestions' in decision['suggestion']
    
    def test_rejection_suggestions(self):
        """測試拒絕時的建議"""
        controller = DecisionController(enable_recording=False)
        
        vss_result = create_vss_result(
            trend=TrendDirection.DOWN,
            confidence=0.9,
        )
        judgment = create_human_judgment(
            trend=TrendDirection.UP,
            confidence=0.9,
        )
        
        decision = controller.process(judgment, vss_result)
        
        assert 'suggestion' in decision
        assert decision['suggestion'].get('action') == 'wait'
        assert decision['suggestion'].get('monitor_again') is True


class TestDecisionControllerStatistics:
    """測試統計功能"""
    
    def test_get_statistics_empty(self):
        """空統計"""
        controller = DecisionController(enable_recording=False)
        
        stats = controller.get_statistics()
        
        assert stats == {}
    
    def test_get_statistics_with_recording(self):
        """有記錄的統計"""
        controller = DecisionController(enable_recording=True)
        
        # 進行一些決策
        vss_result = create_vss_result(
            trend=TrendDirection.UP,
            confidence=0.9,
            risk_level="low",
        )
        judgment = create_human_judgment(
            trend=TrendDirection.UP,
            confidence=0.9,
        )
        
        controller.process(judgment, vss_result)
        
        stats = controller.get_statistics()
        
        assert 'total_decisions' in stats
        assert stats['total_decisions'] >= 1


class TestDecisionControllerAnalysis:
    """測試分析功能"""
    
    def test_analyze_misalignments_empty(self):
        """無不對齊案例"""
        controller = DecisionController(enable_recording=False)
        
        analysis = controller.analyze_misalignments()
        
        assert analysis == []
    
    def test_analyze_misalignments_with_data(self):
        """有不對齊案例"""
        controller = DecisionController(enable_recording=True)
        
        # 添加不對齊案例
        vss_result = create_vss_result(
            trend=TrendDirection.DOWN,
            confidence=0.9,
        )
        judgment = create_human_judgment(
            trend=TrendDirection.UP,
            confidence=0.9,
        )
        
        controller.process(judgment, vss_result)
        
        analysis = controller.analyze_misalignments()
        
        assert len(analysis) >= 1
        assert analysis[0]['human_trend'] == 'up'
        assert analysis[0]['vss_trend'] == 'down'


class TestDecisionControllerEdgeCases:
    """測試邊界情況"""
    
    def test_process_without_recording(self):
        """不使用記錄的處理"""
        controller = DecisionController(enable_recording=False)
        
        vss_result = create_vss_result()
        judgment = create_human_judgment()
        
        decision = controller.process(judgment, vss_result)
        
        # 應該正常工作
        assert 'decision' in decision
    
    def test_process_with_none_callback(self):
        """沒有設置回調"""
        controller = DecisionController(enable_recording=False)
        # 不設置回調
        
        vss_result = create_vss_result(
            trend=TrendDirection.UP,
            confidence=0.9,
            risk_level="low",
        )
        judgment = create_human_judgment(
            trend=TrendDirection.UP,
            confidence=0.9,
        )
        
        decision = controller.process(judgment, vss_result)
        
        # 應該正常工作
        assert 'execution_result' not in decision
    
    def test_process_low_alignment_score(self):
        """低對齊分數"""
        controller = DecisionController(
            alignment_threshold=0.9,  # 高閾值
            enable_recording=False,
        )
        
        vss_result = create_vss_result(
            trend=TrendDirection.UP,
            confidence=0.5,  # 低信心度
        )
        judgment = create_human_judgment(
            trend=TrendDirection.UP,
            confidence=0.5,
        )
        
        decision = controller.process(judgment, vss_result)
        
        assert decision['decision'] is False
        assert decision['alignment_score'] < 0.9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
