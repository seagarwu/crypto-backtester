"""
VSS 類型測試

測試資料結構與類型定義的正確性。
"""

import pytest
from datetime import datetime
from vss.types import (
    TrendDirection,
    PatternType,
    Momentum,
    Volatility,
    SupportResistance,
    MarketState,
    VSSAnalysisResult,
    HumanJudgment,
    AlignmentResult,
)


class TestTrendDirection:
    """測試 TrendDirection 枚舉"""
    
    def test_trend_values(self):
        assert TrendDirection.UP.value == "up"
        assert TrendDirection.DOWN.value == "down"
        assert TrendDirection.SIDEWAYS.value == "sideways"
        assert TrendDirection.UNKNOWN.value == "unknown"
    
    def test_trend_enum_count(self):
        assert len(TrendDirection) == 4


class TestPatternType:
    """測試 PatternType 枚舉"""
    
    def test_pattern_values(self):
        assert PatternType.FLAG.value == "flag"
        assert PatternType.HEAD_SHOULDERS.value == "head_and_shoulders"
        assert PatternType.DOJI.value == "doji"
        assert PatternType.NONE.value == "none"
    
    def test_pattern_enum_count(self):
        # 應該包含所有定義的形態
        assert len(PatternType) > 10


class TestMomentum:
    """測試 Momentum 枚舉"""
    
    def test_momentum_values(self):
        assert Momentum.STRONG_BULL.value == "strong_bull"
        assert Momentum.MODERATE_BULL.value == "moderate_bull"
        assert Momentum.NEUTRAL.value == "neutral"
        assert Momentum.STRONG_BEAR.value == "strong_bear"


class TestVolatility:
    """測試 Volatility 枚舉"""
    
    def test_volatility_values(self):
        assert Volatility.LOW.value == "low"
        assert Volatility.NORMAL.value == "normal"
        assert Volatility.HIGH.value == "high"
        assert Volatility.EXTREME.value == "extreme"


class TestSupportResistance:
    """測試支撐/壓力位資料結構"""
    
    def test_creation(self):
        sr = SupportResistance(
            level=50000.0,
            strength=0.8,
            type="support"
        )
        assert sr.level == 50000.0
        assert sr.strength == 0.8
        assert sr.type == "support"
    
    def test_to_dict(self):
        sr = SupportResistance(
            level=50000.0,
            strength=0.8,
            type="resistance"
        )
        d = sr.__dict__
        assert d['level'] == 50000.0
        assert d['strength'] == 0.8


class TestMarketState:
    """測試市場狀態資料結構"""
    
    def test_creation(self):
        ms = MarketState(
            timestamp=datetime.now(),
            trend=TrendDirection.UP,
            trend_confidence=0.8,
            momentum=Momentum.MODERATE_BULL,
            volatility=Volatility.NORMAL,
            current_price=50000.0,
        )
        
        assert ms.trend == TrendDirection.UP
        assert ms.trend_confidence == 0.8
        assert ms.current_price == 50000.0
    
    def test_to_dict(self):
        ms = MarketState(
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            trend=TrendDirection.DOWN,
            trend_confidence=0.7,
            momentum=Momentum.MODERATE_BEAR,
            volatility=Volatility.HIGH,
            current_price=45000.0,
            description="Test market",
        )
        
        d = ms.to_dict()
        
        assert d['trend'] == 'down'
        assert d['trend_confidence'] == 0.7
        assert d['momentum'] == 'moderate_bear'
        assert d['volatility'] == 'high'
        assert d['current_price'] == 45000.0
        assert 'timestamp' in d


class TestVSSAnalysisResult:
    """測試 VSS 分析結果資料結構"""
    
    def test_creation(self):
        market_state = MarketState(
            timestamp=datetime.now(),
            trend=TrendDirection.UP,
            trend_confidence=0.8,
            momentum=Momentum.MODERATE_BULL,
            volatility=Volatility.NORMAL,
            current_price=50000.0,
        )
        
        result = VSSAnalysisResult(
            timestamp=datetime.now(),
            symbol="BTCUSDT",
            interval="1h",
            market_state=market_state,
            price_change_pct=5.0,
            volume_ratio=1.2,
            risk_level="medium",
        )
        
        assert result.symbol == "BTCUSDT"
        assert result.interval == "1h"
        assert result.price_change_pct == 5.0
        assert result.risk_level == "medium"
    
    def test_to_dict(self):
        market_state = MarketState(
            timestamp=datetime.now(),
            trend=TrendDirection.SIDEWAYS,
            trend_confidence=0.5,
            momentum=Momentum.NEUTRAL,
            volatility=Volatility.NORMAL,
            current_price=50000.0,
        )
        
        result = VSSAnalysisResult(
            timestamp=datetime(2024, 1, 1),
            symbol="ETHUSDT",
            interval="4h",
            market_state=market_state,
            price_change_pct=1.5,
            volume_ratio=0.8,
            observations=["Test observation"],
            risk_level="low",
        )
        
        d = result.to_dict()
        
        assert d['symbol'] == 'ETHUSDT'
        assert d['interval'] == '4h'
        assert d['price_change_pct'] == 1.5
        assert d['risk_level'] == 'low'
        assert 'market_state' in d


class TestHumanJudgment:
    """測試人類判斷資料結構"""
    
    def test_creation(self):
        judgment = HumanJudgment(
            timestamp=datetime.now(),
            symbol="BTCUSDT",
            interval="1h",
            trend=TrendDirection.UP,
            confidence=0.75,
            notes="看到突破信號",
            pattern_observed=PatternType.FLAG,
        )
        
        assert judgment.symbol == "BTCUSDT"
        assert judgment.trend == TrendDirection.UP
        assert judgment.confidence == 0.75
        assert judgment.pattern_observed == PatternType.FLAG
    
    def test_to_dict(self):
        judgment = HumanJudgment(
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            symbol="BTCUSDT",
            interval="1h",
            trend=TrendDirection.DOWN,
            confidence=0.6,
        )
        
        d = judgment.to_dict()
        
        assert d['symbol'] == 'BTCUSDT'
        assert d['trend'] == 'down'
        assert d['confidence'] == 0.6
        assert 'timestamp' in d


class TestAlignmentResult:
    """測試對齊結果資料結構"""
    
    def test_creation(self):
        market_state = MarketState(
            timestamp=datetime.now(),
            trend=TrendDirection.UP,
            trend_confidence=0.8,
            momentum=Momentum.MODERATE_BULL,
            volatility=Volatility.NORMAL,
            current_price=50000.0,
        )
        
        vss_result = VSSAnalysisResult(
            timestamp=datetime.now(),
            symbol="BTCUSDT",
            interval="1h",
            market_state=market_state,
            price_change_pct=5.0,
            volume_ratio=1.2,
        )
        
        human = HumanJudgment(
            timestamp=datetime.now(),
            symbol="BTCUSDT",
            interval="1h",
            trend=TrendDirection.UP,
            confidence=0.75,
        )
        
        alignment = AlignmentResult(
            timestamp=datetime.now(),
            human_judgment=human,
            vss_result=vss_result,
            trend_match=True,
            alignment_score=0.85,
            can_execute=True,
            reason="對齊良好",
        )
        
        assert alignment.trend_match is True
        assert alignment.alignment_score == 0.85
        assert alignment.can_execute is True
    
    def test_to_dict(self):
        market_state = MarketState(
            timestamp=datetime.now(),
            trend=TrendDirection.UP,
            trend_confidence=0.8,
            momentum=Momentum.MODERATE_BULL,
            volatility=Volatility.NORMAL,
            current_price=50000.0,
        )
        
        vss_result = VSSAnalysisResult(
            timestamp=datetime.now(),
            symbol="BTCUSDT",
            interval="1h",
            market_state=market_state,
            price_change_pct=5.0,
            volume_ratio=1.2,
        )
        
        human = HumanJudgment(
            timestamp=datetime.now(),
            symbol="BTCUSDT",
            interval="1h",
            trend=TrendDirection.UP,
            confidence=0.75,
        )
        
        alignment = AlignmentResult(
            timestamp=datetime.now(),
            human_judgment=human,
            vss_result=vss_result,
            trend_match=True,
            alignment_score=0.85,
        )
        
        d = alignment.to_dict()
        
        assert d['trend_match'] is True
        assert d['alignment_score'] == 0.85
        assert 'human_judgment' in d
        assert 'vss_result' in d


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
