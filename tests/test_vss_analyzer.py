"""
VSS 分析器測試

測試 VSS 分析引擎的功能正確性。
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from vss.analyzer import VSSAnalyzer
from vss.types import (
    TrendDirection,
    PatternType,
    Momentum,
    Volatility,
)


def generate_test_data(
    n_bars: int = 100,
    trend: str = "sideways",
    volatility: float = 0.02,
    seed: int = 42
) -> pd.DataFrame:
    """生成測試用 K 線數據"""
    np.random.seed(seed)
    
    dates = pd.date_range(start='2024-01-01', periods=n_bars, freq='1h')
    base_price = 50000
    
    # 根據趨勢生成價格
    if trend == "up":
        trend_factor = np.linspace(0, 0.1, n_bars)
    elif trend == "down":
        trend_factor = np.linspace(0, -0.1, n_bars)
    else:
        trend_factor = np.zeros(n_bars)
    
    noise = np.random.randn(n_bars) * volatility
    prices = base_price * (1 + trend_factor + noise)
    
    # 生成 OHLCV
    df = pd.DataFrame({
        'open': prices * (1 + np.random.randn(n_bars) * 0.002),
        'high': prices * (1 + np.abs(np.random.randn(n_bars) * 0.005)),
        'low': prices * (1 - np.abs(np.random.randn(n_bars) * 0.005)),
        'close': prices,
        'volume': np.random.randint(1000, 10000, n_bars),
    }, index=dates)
    
    # 確保數據正確
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)
    
    return df


class TestVSSAnalyzerInit:
    """測試分析器初始化"""
    
    def test_default_init(self):
        analyzer = VSSAnalyzer()
        assert analyzer.short_window == 20
        assert analyzer.long_window == 50
        assert analyzer.volume_ma_period == 20
    
    def test_custom_init(self):
        analyzer = VSSAnalyzer(
            short_window=10,
            long_window=100,
            volume_ma_period=30,
        )
        assert analyzer.short_window == 10
        assert analyzer.long_window == 100
        assert analyzer.volume_ma_period == 30


class TestVSSAnalyzerIndicators:
    """測試技術指標計算"""
    
    def test_calculate_indicators(self):
        df = generate_test_data(100)
        analyzer = VSSAnalyzer()
        
        indicators = analyzer._calculate_indicators(df)
        
        # 檢查必要的指標
        assert 'sma_short' in indicators
        assert 'sma_long' in indicators
        assert 'rsi' in indicators
        assert 'atr' in indicators
        assert 'macd' in indicators
        
        # 指標應該有數值（至少最後一根）
        assert indicators['sma_short'] is not None
        assert indicators['rsi'] is not None
    
    def test_indicators_with_insufficient_data(self):
        df = generate_test_data(10)
        analyzer = VSSAnalyzer()
        
        indicators = analyzer._calculate_indicators(df)
        
        # 數據不足時可能為 None
        assert indicators is not None


class TestVSSAnalyzerTrend:
    """測試趨勢判斷"""
    
    def test_uptrend_detection(self):
        # 明顯上升趨勢
        df = generate_test_data(100, trend="up", volatility=0.01)
        analyzer = VSSAnalyzer()
        indicators = analyzer._calculate_indicators(df)
        
        trend, confidence = analyzer._determine_trend(df, indicators)
        
        # 上升趨勢應該被識別
        assert trend in [TrendDirection.UP, TrendDirection.SIDEWAYS]
        assert 0 <= confidence <= 1
    
    def test_downtrend_detection(self):
        # 明顯下降趨勢
        df = generate_test_data(100, trend="down", volatility=0.01)
        analyzer = VSSAnalyzer()
        indicators = analyzer._calculate_indicators(df)
        
        trend, confidence = analyzer._determine_trend(df, indicators)
        
        # 下降趨勢應該被識別
        assert trend in [TrendDirection.DOWN, TrendDirection.SIDEWAYS]
        assert 0 <= confidence <= 1
    
    def test_sideways_detection(self):
        # 盤整市場
        df = generate_test_data(100, trend="sideways", volatility=0.01)
        analyzer = VSSAnalyzer()
        indicators = analyzer._calculate_indicators(df)
        
        trend, confidence = analyzer._determine_trend(df, indicators)
        
        assert trend in TrendDirection
        assert 0 <= confidence <= 1


class TestVSSAnalyzerMomentum:
    """測試動能判斷"""
    
    def test_momentum_strong_bull(self):
        analyzer = VSSAnalyzer()
        
        # RSI >= 70 且 MACD 為正 = 強多
        momentum = analyzer._determine_momentum({
            'rsi': 75,
            'macd_hist': 10,
        })
        assert momentum == Momentum.STRONG_BULL
    
    def test_momentum_strong_bull_positive(self):
        analyzer = VSSAnalyzer()
        
        momentum = analyzer._determine_momentum({
            'rsi': 75,
            'macd_hist': 5,
        })
        assert momentum == Momentum.STRONG_BULL
    
    def test_momentum_neutral(self):
        analyzer = VSSAnalyzer()
        
        momentum = analyzer._determine_momentum({
            'rsi': 50,
            'macd_hist': 0,
        })
        assert momentum == Momentum.NEUTRAL
    
    def test_momentum_oversold(self):
        analyzer = VSSAnalyzer()
        
        momentum = analyzer._determine_momentum({
            'rsi': 25,
            'macd_hist': 5,
        })
        assert momentum == Momentum.STRONG_BULL  # 可能反彈
    
    def test_momentum_none_rsi(self):
        analyzer = VSSAnalyzer()
        
        momentum = analyzer._determine_momentum({})
        assert momentum == Momentum.NEUTRAL


class TestVSSAnalyzerVolatility:
    """測試波動率判斷"""
    
    def test_volatility_low(self):
        analyzer = VSSAnalyzer()
        
        volatility = analyzer._determine_volatility({
            'volatility_pct': 0.5,
        })
        assert volatility == Volatility.LOW
    
    def test_volatility_normal(self):
        analyzer = VSSAnalyzer()
        
        volatility = analyzer._determine_volatility({
            'volatility_pct': 2.0,
        })
        assert volatility == Volatility.NORMAL
    
    def test_volatility_high(self):
        analyzer = VSSAnalyzer()
        
        volatility = analyzer._determine_volatility({
            'volatility_pct': 4.0,
        })
        assert volatility == Volatility.HIGH
    
    def test_volatility_extreme(self):
        analyzer = VSSAnalyzer()
        
        volatility = analyzer._determine_volatility({
            'volatility_pct': 6.0,
        })
        assert volatility == Volatility.EXTREME
    
    def test_volatility_none(self):
        analyzer = VSSAnalyzer()
        
        volatility = analyzer._determine_volatility({})
        assert volatility == Volatility.NORMAL


class TestVSSAnalyzerFullAnalysis:
    """測試完整分析流程"""
    
    def test_analyze_basic(self):
        df = generate_test_data(100)
        analyzer = VSSAnalyzer()
        
        result = analyzer.analyze(df, symbol="BTCUSDT", interval="1h")
        
        assert result.symbol == "BTCUSDT"
        assert result.interval == "1h"
        assert result.market_state is not None
        assert result.price_change_pct is not None
        assert result.volume_ratio is not None
    
    def test_analyze_observations(self):
        df = generate_test_data(100)
        analyzer = VSSAnalyzer()
        
        result = analyzer.analyze(df)
        
        # 應該有觀察筆記
        assert isinstance(result.observations, list)
        assert len(result.observations) > 0
    
    def test_analyze_risk_level(self):
        df = generate_test_data(100)
        analyzer = VSSAnalyzer()
        
        result = analyzer.analyze(df)
        
        # 風險等級應該是 low/medium/high 之一
        assert result.risk_level in ['low', 'medium', 'high']
    
    def test_analyze_output_dict(self):
        df = generate_test_data(100)
        analyzer = VSSAnalyzer()
        
        result = analyzer.analyze(df, symbol="ETHUSDT", interval="4h")
        d = result.to_dict()
        
        assert d['symbol'] == 'ETHUSDT'
        assert d['interval'] == '4h'
        assert 'market_state' in d
        assert 'observations' in d


class TestVSSAnalyzerPriceChange:
    """測試價格變化計算"""
    
    def test_calculate_price_change(self):
        df = generate_test_data(50, trend="up")
        analyzer = VSSAnalyzer()
        
        change = analyzer._calculate_price_change(df)
        
        # 變化率應該是數字
        assert isinstance(change, (int, float))
    
    def test_calculate_price_change_insufficient(self):
        df = generate_test_data(1)
        analyzer = VSSAnalyzer()
        
        change = analyzer._calculate_price_change(df)
        assert change == 0.0


class TestVSSAnalyzerVolume:
    """測試成交量分析"""
    
    def test_analyze_volume_normal(self):
        df = generate_test_data(50)
        analyzer = VSSAnalyzer()
        
        status = analyzer._analyze_volume(df)
        
        assert status in ['low', 'normal', 'high', 'spike']
    
    def test_analyze_volume_no_volume_column(self):
        df = generate_test_data(50)
        del df['volume']
        
        analyzer = VSSAnalyzer()
        status = analyzer._analyze_volume(df)
        
        assert status == 'normal'


class TestVSSAnalyzerDescription:
    """測試市場描述生成"""
    
    def test_generate_description(self):
        analyzer = VSSAnalyzer()
        
        desc = analyzer._generate_description(
            trend=TrendDirection.UP,
            momentum=Momentum.MODERATE_BULL,
            volatility=Volatility.NORMAL,
            pattern=PatternType.NONE,
        )
        
        assert isinstance(desc, str)
        assert len(desc) > 0
        assert '多頭' in desc or '上升' in desc


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
