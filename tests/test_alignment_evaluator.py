"""
對齊評估器測試

測試 AlignmentEvaluator 的對齊評估邏輯。
"""

import pytest
from datetime import datetime

from alignment.evaluator import AlignmentEvaluator
from vss.types import (
    HumanJudgment,
    VSSAnalysisResult,
    MarketState,
    TrendDirection,
    PatternType,
    Momentum,
    Volatility,
)


def create_market_state(
    trend: TrendDirection = TrendDirection.UP,
    confidence: float = 0.8,
    pattern: PatternType = PatternType.NONE,
) -> MarketState:
    """創建測試用市場狀態"""
    return MarketState(
        timestamp=datetime.now(),
        trend=trend,
        trend_confidence=confidence,
        momentum=Momentum.MODERATE_BULL,
        volatility=Volatility.NORMAL,
        current_price=50000.0,
        pattern=pattern,
        pattern_confidence=0.5,
    )


def create_vss_result(
    trend: TrendDirection = TrendDirection.UP,
    confidence: float = 0.8,
    pattern: PatternType = PatternType.NONE,
    risk_level: str = "medium",
) -> VSSAnalysisResult:
    """創建測試用 VSS 分析結果"""
    return VSSAnalysisResult(
        timestamp=datetime.now(),
        symbol="BTCUSDT",
        interval="1h",
        market_state=create_market_state(trend, confidence, pattern),
        price_change_pct=5.0,
        volume_ratio=1.2,
        risk_level=risk_level,
    )


def create_human_judgment(
    trend: TrendDirection = TrendDirection.UP,
    confidence: float = 0.75,
    pattern: PatternType = None,
) -> HumanJudgment:
    """創建測試用人類判斷"""
    return HumanJudgment(
        timestamp=datetime.now(),
        symbol="BTCUSDT",
        interval="1h",
        trend=trend,
        confidence=confidence,
        notes="Test judgment",
        pattern_observed=pattern,
    )


class TestAlignmentEvaluatorInit:
    """測試評估器初始化"""
    
    def test_default_init(self):
        evaluator = AlignmentEvaluator()
        
        assert evaluator.alignment_threshold == 0.7
        assert evaluator.confidence_threshold == 0.6
    
    def test_custom_init(self):
        evaluator = AlignmentEvaluator(
            alignment_threshold=0.8,
            confidence_threshold=0.7,
        )
        
        assert evaluator.alignment_threshold == 0.8
        assert evaluator.confidence_threshold == 0.7


class TestAlignmentEvaluatorPerfectMatch:
    """測試完全匹配情況"""
    
    def test_perfect_alignment(self):
        """人類與 VSS 判斷完全一致"""
        evaluator = AlignmentEvaluator()
        
        vss_result = create_vss_result(
            trend=TrendDirection.UP,
            confidence=0.8,
        )
        human = create_human_judgment(
            trend=TrendDirection.UP,
            confidence=0.8,
        )
        
        result = evaluator.evaluate(human, vss_result)
        
        assert result.trend_match is True
        assert result.alignment_score > 0.8
    
    def test_opposite_trend(self):
        """人類與 VSS 判斷完全相反"""
        evaluator = AlignmentEvaluator()
        
        vss_result = create_vss_result(
            trend=TrendDirection.DOWN,
            confidence=0.9,
        )
        human = create_human_judgment(
            trend=TrendDirection.UP,
            confidence=0.9,
        )
        
        result = evaluator.evaluate(human, vss_result)
        
        assert result.trend_match is False
        # 趨勢相反但信心度高，分數會有基礎分
        assert result.alignment_score < 0.5


class TestAlignmentEvaluatorConfidence:
    """測試信心度影響"""
    
    def test_low_confidence_rejection(self):
        """信心度不足應該拒絕"""
        evaluator = AlignmentEvaluator()
        
        vss_result = create_vss_result(
            trend=TrendDirection.UP,
            confidence=0.3,  # 低信心度
        )
        human = create_human_judgment(
            trend=TrendDirection.UP,
            confidence=0.3,
        )
        
        result = evaluator.evaluate(human, vss_result)
        
        # 應該被拒絕
        assert result.can_execute is False
        assert "信心度" in result.reason
    
    def test_high_confidence_approval(self):
        """高信心度應該批准"""
        evaluator = AlignmentEvaluator()
        
        vss_result = create_vss_result(
            trend=TrendDirection.UP,
            confidence=0.9,
        )
        human = create_human_judgment(
            trend=TrendDirection.UP,
            confidence=0.9,
        )
        
        result = evaluator.evaluate(human, vss_result)
        
        # 應該被批准
        assert result.can_execute is True


class TestAlignmentEvaluatorRisk:
    """測試風險評估"""
    
    def test_high_risk_rejection(self):
        """高風險應該拒絕"""
        evaluator = AlignmentEvaluator()
        
        vss_result = create_vss_result(
            trend=TrendDirection.UP,
            confidence=0.9,
            risk_level="high",
        )
        human = create_human_judgment(
            trend=TrendDirection.UP,
            confidence=0.9,
        )
        
        result = evaluator.evaluate(human, vss_result)
        
        assert result.can_execute is False
        assert "風險" in result.reason
    
    def test_low_risk_approval(self):
        """低風險應該批准"""
        evaluator = AlignmentEvaluator()
        
        vss_result = create_vss_result(
            trend=TrendDirection.UP,
            confidence=0.8,
            risk_level="low",
        )
        human = create_human_judgment(
            trend=TrendDirection.UP,
            confidence=0.8,
        )
        
        result = evaluator.evaluate(human, vss_result)
        
        assert result.can_execute is True


class TestAlignmentEvaluatorUnknownTrend:
    """測試趨勢未知情況"""
    
    def test_unknown_trend_rejection(self):
        """趨勢未知應該拒絕"""
        evaluator = AlignmentEvaluator()
        
        vss_result = create_vss_result(
            trend=TrendDirection.UNKNOWN,
            confidence=0.5,
        )
        human = create_human_judgment(
            trend=TrendDirection.UNKNOWN,
            confidence=0.5,
        )
        
        result = evaluator.evaluate(human, vss_result)
        
        assert result.can_execute is False
        assert "趨勢" in result.reason


class TestAlignmentEvaluatorPattern:
    """測試形態識別影響"""
    
    def test_pattern_match(self):
        """形態匹配應該提高分數"""
        evaluator = AlignmentEvaluator()
        
        vss_result = create_vss_result(
            trend=TrendDirection.UP,
            confidence=0.7,
            pattern=PatternType.FLAG,
        )
        human = create_human_judgment(
            trend=TrendDirection.UP,
            confidence=0.7,
            pattern=PatternType.FLAG,
        )
        
        result = evaluator.evaluate(human, vss_result)
        
        assert result.trend_match is True
    
    def test_pattern_mismatch(self):
        """形態不匹配"""
        evaluator = AlignmentEvaluator()
        
        vss_result = create_vss_result(
            trend=TrendDirection.UP,
            confidence=0.7,
            pattern=PatternType.FLAG,
        )
        human = create_human_judgment(
            trend=TrendDirection.UP,
            confidence=0.7,
            pattern=PatternType.HEAD_SHOULDERS,
        )
        
        result = evaluator.evaluate(human, vss_result)
        
        assert result.trend_match is True  # 趨勢仍然匹配
        assert "形態" in result.difference_notes  # 但有差異說明


class TestAlignmentEvaluatorDifferenceNotes:
    """測試差異說明"""
    
    def test_no_difference(self):
        """無差異時應該有適當說明"""
        evaluator = AlignmentEvaluator()
        
        vss_result = create_vss_result(
            trend=TrendDirection.UP,
            confidence=0.8,
        )
        human = create_human_judgment(
            trend=TrendDirection.UP,
            confidence=0.8,
        )
        
        result = evaluator.evaluate(human, vss_result)
        
        # 應該說明一致
        assert "一致" in result.difference_notes or result.difference_notes != ""
    
    def test_confidence_difference(self):
        """信心度差異應該被記錄"""
        evaluator = AlignmentEvaluator()
        
        vss_result = create_vss_result(
            trend=TrendDirection.UP,
            confidence=0.9,
        )
        human = create_human_judgment(
            trend=TrendDirection.UP,
            confidence=0.3,  # 很大的信心度差異
        )
        
        result = evaluator.evaluate(human, vss_result)
        
        assert "信心度" in result.difference_notes


class TestAlignmentEvaluatorBatch:
    """測試批量評估"""
    
    def test_batch_evaluate(self):
        """批量評估應該返回正確數量的結果"""
        evaluator = AlignmentEvaluator()
        
        judgments = [
            create_human_judgment(TrendDirection.UP, 0.8),
            create_human_judgment(TrendDirection.DOWN, 0.7),
        ]
        vss_results = [
            create_vss_result(TrendDirection.UP, 0.8),
            create_vss_result(TrendDirection.DOWN, 0.7),
        ]
        
        results = evaluator.batch_evaluate(judgments, vss_results)
        
        assert len(results) == 2
        assert results[0].trend_match is True
        assert results[1].trend_match is True


class TestAlignmentEvaluatorEdgeCases:
    """測試邊界情況"""
    
    def test_both_unknown_trend(self):
        """雙方都未知"""
        evaluator = AlignmentEvaluator()
        
        vss_result = create_vss_result(
            trend=TrendDirection.UNKNOWN,
            confidence=0.5,
        )
        human = create_human_judgment(
            trend=TrendDirection.UNKNOWN,
            confidence=0.5,
        )
        
        result = evaluator.evaluate(human, vss_result)
        
        # 趨勢不匹配因為雙方都是 UNKNOWN
        assert result.can_execute is False
    
    def test_sideways_trend(self):
        """盤整趨勢"""
        evaluator = AlignmentEvaluator()
        
        vss_result = create_vss_result(
            trend=TrendDirection.SIDEWAYS,
            confidence=0.7,
        )
        human = create_human_judgment(
            trend=TrendDirection.SIDEWAYS,
            confidence=0.7,
        )
        
        result = evaluator.evaluate(human, vss_result)
        
        assert result.trend_match is True
        assert result.can_execute is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
