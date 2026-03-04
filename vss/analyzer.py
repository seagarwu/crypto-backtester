"""
VSS 分析引擎

分析市場數據，輸出結構化的市場狀態描述。
模擬人類交易者對 K 線圖的直觀理解。
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional

from .types import (
    VSSAnalysisResult,
    MarketState,
    TrendDirection,
    PatternType,
    Momentum,
    Volatility,
    SupportResistance,
)


class VSSAnalyzer:
    """
    VSS 分析引擎
    
    將市場數據轉換為結構化的市場狀態描述，
    類似人類交易者看圖時的認知過程。
    """
    
    def __init__(
        self,
        short_window: int = 20,
        long_window: int = 50,
        volume_ma_period: int = 20,
    ):
        """
        初始化分析器
        
        Args:
            short_window: 短期均線週期
            long_window: 長期均線週期
            volume_ma_period: 成交量均線週期
        """
        self.short_window = short_window
        self.long_window = long_window
        self.volume_ma_period = volume_ma_period
    
    def analyze(
        self,
        df: pd.DataFrame,
        symbol: str = "UNKNOWN",
        interval: str = "1h",
    ) -> VSSAnalysisResult:
        """
        分析市場數據
        
        Args:
            df: 必須包含 open, high, low, close, volume 欄位
            symbol: 交易標的
            interval: 時間週期
            
        Returns:
            VSSAnalysisResult: 結構化分析結果
        """
        # 計算技術指標
        indicators = self._calculate_indicators(df)
        
        # 判斷市場狀態
        market_state = self._determine_market_state(df, indicators)
        
        # 計算價格變化
        price_change_pct = self._calculate_price_change(df)
        
        # 成交量分析
        volume_ratio = self._calculate_volume_ratio(df)
        
        # 風險評估
        risk_level = self._assess_risk(market_state, indicators)
        
        # 觀察筆記
        observations = self._generate_observations(df, indicators, market_state)
        
        return VSSAnalysisResult(
            timestamp=datetime.now(),
            symbol=symbol,
            interval=interval,
            market_state=market_state,
            price_change_pct=price_change_pct,
            volume_ratio=volume_ratio,
            indicators=indicators,
            observations=observations,
            risk_level=risk_level,
        )
    
    def _calculate_indicators(self, df: pd.DataFrame) -> dict:
        """計算技術指標"""
        close = df['close']
        
        # 均線
        sma_short = close.rolling(window=self.short_window).mean()
        sma_long = close.rolling(window=self.long_window).mean()
        
        # RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # ATR (Average True Range) - 波動率
        high_low = df['high'] - df['low']
        high_close = (df['high'] - close.shift(1)).abs()
        low_close = (df['low'] - close.shift(1)).abs()
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=14).mean()
        
        # 波動率 (ATR / Close * 100)
        volatility_pct = (atr / close) * 100
        
        # MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        macd_hist = macd - signal
        
        return {
            "sma_short": sma_short.iloc[-1] if len(sma_short) > 0 else None,
            "sma_long": sma_long.iloc[-1] if len(sma_long) > 0 else None,
            "rsi": rsi.iloc[-1] if len(rsi) > 0 else None,
            "atr": atr.iloc[-1] if len(atr) > 0 else None,
            "volatility_pct": volatility_pct.iloc[-1] if len(volatility_pct) > 0 else None,
            "macd": macd.iloc[-1] if len(macd) > 0 else None,
            "macd_signal": signal.iloc[-1] if len(signal) > 0 else None,
            "macd_hist": macd_hist.iloc[-1] if len(macd_hist) > 0 else None,
        }
    
    def _determine_market_state(
        self,
        df: pd.DataFrame,
        indicators: dict
    ) -> MarketState:
        """判斷市場狀態"""
        close = df['close']
        current_price = close.iloc[-1]
        
        # 趨勢判斷
        trend, trend_confidence = self._determine_trend(df, indicators)
        
        # 動能判斷
        momentum = self._determine_momentum(indicators)
        
        # 波動率判斷
        volatility = self._determine_volatility(indicators)
        
        # 支撐/壓力位
        support, resistance = self._find_support_resistance(df)
        
        # 形態識別
        pattern, pattern_confidence = self._detect_pattern(df)
        
        # 成交量狀態
        volume_status = self._analyze_volume(df)
        
        # 生成描述
        description = self._generate_description(
            trend, momentum, volatility, pattern
        )
        
        return MarketState(
            timestamp=datetime.now(),
            trend=trend,
            trend_confidence=trend_confidence,
            momentum=momentum,
            volatility=volatility,
            current_price=current_price,
            nearest_support=support,
            nearest_resistance=resistance,
            pattern=pattern,
            pattern_confidence=pattern_confidence,
            volume_status=volume_status,
            description=description,
        )
    
    def _determine_trend(
        self,
        df: pd.DataFrame,
        indicators: dict
    ) -> tuple[TrendDirection, float]:
        """判斷趨勢"""
        close = df['close']
        sma_short = indicators.get("sma_short")
        sma_long = indicators.get("sma_long")
        rsi = indicators.get("rsi")
        
        if sma_short is None or sma_long is None:
            return TrendDirection.UNKNOWN, 0.0
        
        # 計算近期價格變化
        recent_change = (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5] * 100 if len(close) >= 5 else 0
        
        # 均線判斷
        ma_bullish = sma_short > sma_long
        price_above_ma = close.iloc[-1] > sma_short
        
        # 多因素綜合判斷
        bullish_signals = 0
        total_signals = 0
        
        # 均線多頭排列
        total_signals += 1
        if ma_bullish:
            bullish_signals += 1
        
        # 價格在均線上方
        total_signals += 1
        if price_above_ma:
            bullish_signals += 1
        
        # RSI 偏多
        total_signals += 1
        if rsi and 50 < rsi < 70:
            bullish_signals += 0.5
        elif rsi and rsi >= 70:
            bullish_signals += 1
        elif rsi and rsi < 30:
            bullish_signals -= 0.5
        
        # 近期漲跌
        total_signals += 1
        if recent_change > 2:
            bullish_signals += 1
        elif recent_change < -2:
            bullish_signals -= 1
        
        # 計算信心度
        confidence = abs(bullish_signals) / total_signals
        
        if bullish_signals > 1:
            return TrendDirection.UP, min(confidence, 1.0)
        elif bullish_signals < -1:
            return TrendDirection.DOWN, min(confidence, 1.0)
        else:
            return TrendDirection.SIDEWAYS, min(confidence, 1.0)
    
    def _determine_momentum(self, indicators: dict) -> Momentum:
        """判斷動能"""
        rsi = indicators.get("rsi")
        macd_hist = indicators.get("macd_hist")
        
        if rsi is None:
            return Momentum.NEUTRAL
        
        # RSI 區間
        if rsi >= 70:
            if macd_hist and macd_hist < 0:
                return Momentum.STRONG_BEAR  # 可能有回調
            return Momentum.STRONG_BULL
        elif rsi >= 60:
            return Momentum.MODERATE_BULL
        elif rsi >= 40:
            return Momentum.NEUTRAL
        elif rsi >= 30:
            return Momentum.MODERATE_BEAR
        else:
            if macd_hist and macd_hist > 0:
                return Momentum.STRONG_BULL  # 可能反彈
            return Momentum.STRONG_BEAR
    
    def _determine_volatility(self, indicators: dict) -> Volatility:
        """判斷波動率"""
        volatility_pct = indicators.get("volatility_pct")
        
        if volatility_pct is None:
            return Volatility.NORMAL
        
        # 比特幣的波動率參考值
        if volatility_pct < 1:
            return Volatility.LOW
        elif volatility_pct < 3:
            return Volatility.NORMAL
        elif volatility_pct < 5:
            return Volatility.HIGH
        else:
            return Volatility.EXTREME
    
    def _find_support_resistance(
        self,
        df: pd.DataFrame
    ) -> tuple[Optional[SupportResistance], Optional[SupportResistance]]:
        """找尋支撐/壓力位"""
        close = df['close']
        recent_prices = close.iloc[-20:]  # 最近20根
        
        # 簡單方法：找局部高低點
        current = close.iloc[-1]
        
        # 支撐：找最近的低點群
        recent_lows = recent_prices[recent_prices < recent_prices.rolling(5).min().shift(1)]
        if len(recent_lows) > 0:
            support_level = recent_lows.min()
            support = SupportResistance(
                level=support_level,
                strength=0.5,
                type="support"
            )
        else:
            support = None
        
        # 壓力：找最近的高點群
        recent_highs = recent_prices[recent_prices > recent_prices.rolling(5).max().shift(1)]
        if len(recent_highs) > 0:
            resistance_level = recent_highs.max()
            resistance = SupportResistance(
                level=resistance_level,
                strength=0.5,
                type="resistance"
            )
        else:
            resistance = None
        
        return support, resistance
    
    def _detect_pattern(
        self,
        df: pd.DataFrame
    ) -> tuple[PatternType, float]:
        """檢測圖形模式 - 簡化版本"""
        close = df['close']
        
        if len(close) < 20:
            return PatternType.NONE, 0.0
        
        # 取得最近資料
        recent = close.iloc[-20:]
        
        # 計算趨勢
        first_half = recent.iloc[:10].mean()
        second_half = recent.iloc[10:].mean()
        
        # 計算波動
        std = recent.std()
        range_pct = (recent.max() - recent.min()) / recent.min()
        
        # 簡易形態識別
        if range_pct < 0.02:
            if abs(recent.iloc[-1] - recent.iloc[-5]) < std * 0.5:
                return PatternType.RANGE, 0.6
        
        # 上升趨勢中的盤整
        if second_half > first_half and range_pct < 0.05:
            return PatternType.FLAG, 0.5
        
        # 下降趨勢中的盤整
        if second_half < first_half and range_pct < 0.05:
            return PatternType.FLAG, 0.5
        
        return PatternType.NONE, 0.0
    
    def _analyze_volume(self, df: pd.DataFrame) -> str:
        """分析成交量"""
        if 'volume' not in df.columns:
            return "normal"
        
        volume = df['volume']
        volume_ma = volume.rolling(window=self.volume_ma_period).mean()
        
        if len(volume) == 0:
            return "normal"
        
        current_volume = volume.iloc[-1]
        avg_volume = volume_ma.iloc[-1] if len(volume_ma) > 0 else current_volume
        
        if avg_volume == 0:
            return "normal"
        
        ratio = current_volume / avg_volume
        
        if ratio < 0.5:
            return "low"
        elif ratio > 2:
            return "spike"
        elif ratio > 1.5:
            return "high"
        else:
            return "normal"
    
    def _calculate_price_change(self, df: pd.DataFrame) -> float:
        """計算價格變化百分比"""
        close = df['close']
        
        if len(close) < 2:
            return 0.0
        
        # 計算 N 根 K 棒後的變化
        period = min(20, len(close) - 1)
        change = (close.iloc[-1] - close.iloc[-period-1]) / close.iloc[-period-1] * 100
        
        return change
    
    def _calculate_volume_ratio(self, df: pd.DataFrame) -> float:
        """計算成交量比率"""
        if 'volume' not in df.columns:
            return 1.0
        
        volume = df['volume']
        volume_ma = volume.rolling(window=self.volume_ma_period).mean()
        
        if len(volume_ma) == 0 or volume_ma.iloc[-1] == 0:
            return 1.0
        
        return volume.iloc[-1] / volume_ma.iloc[-1]
    
    def _assess_risk(
        self,
        market_state: MarketState,
        indicators: dict
    ) -> str:
        """評估風險"""
        risk_score = 0
        
        # 波動率高風險
        if market_state.volatility == Volatility.HIGH:
            risk_score += 1
        elif market_state.volatility == Volatility.EXTREME:
            risk_score += 2
        
        # 趨勢不明確
        if market_state.trend == TrendDirection.UNKNOWN:
            risk_score += 1
        elif market_state.trend == TrendDirection.SIDEWAYS:
            risk_score += 0.5
        
        # RSI 極值
        rsi = indicators.get("rsi")
        if rsi:
            if rsi >= 80 or rsi <= 20:
                risk_score += 1
            elif rsi >= 70 or rsi <= 30:
                risk_score += 0.5
        
        # 成交量異常
        if market_state.volume_status == "spike":
            risk_score += 1
        
        if risk_score >= 3:
            return "high"
        elif risk_score >= 1.5:
            return "medium"
        else:
            return "low"
    
    def _generate_observations(
        self,
        df: pd.DataFrame,
        indicators: dict,
        market_state: MarketState
    ) -> list[str]:
        """生成觀察筆記"""
        observations = []
        
        # 趨勢觀察
        if market_state.trend == TrendDirection.UP:
            observations.append(f"價格處於上升趨勢（信心度: {market_state.trend_confidence:.0%}）")
        elif market_state.trend == TrendDirection.DOWN:
            observations.append(f"價格處於下降趨勢（信心度: {market_state.trend_confidence:.0%}）")
        else:
            observations.append("價格趨勢不明確，處於盤整狀態")
        
        # RSI 觀察
        rsi = indicators.get("rsi")
        if rsi:
            if rsi >= 70:
                observations.append(f"RSI 處於超買區域 ({rsi:.1f})")
            elif rsi <= 30:
                observations.append(f"RSI 處於超賣區域 ({rsi:.1f})")
        
        # 成交量觀察
        if market_state.volume_status == "spike":
            observations.append("成交量急增，需留意趨勢變化")
        elif market_state.volume_status == "low":
            observations.append("成交量低迷，市場參與度不足")
        
        # 形態觀察
        if market_state.pattern != PatternType.NONE:
            observations.append(f"偵測到圖形模式: {market_state.pattern.value}")
        
        return observations
       
    def _generate_description(
        self,
        trend: TrendDirection,
        momentum: Momentum,
        volatility: Volatility,
        pattern: PatternType
    ) -> str:
        """生成市場狀態描述"""
        trend_text = {
            TrendDirection.UP: "多頭",
            TrendDirection.DOWN: "空頭",
            TrendDirection.SIDEWAYS: "盤整",
            TrendDirection.UNKNOWN: "趨勢不明",
        }.get(trend, "未知")
        
        momentum_text = {
            Momentum.STRONG_BULL: "強勢",
            Momentum.MODERATE_BULL: "偏多",
            Momentum.NEUTRAL: "中性",
            Momentum.MODERATE_BEAR: "偏空",
            Momentum.STRONG_BEAR: "強勢",
        }.get(momentum, "未知")
        
        volatility_text = {
            Volatility.LOW: "低波動",
            Volatility.NORMAL: "正常波動",
            Volatility.HIGH: "高波動",
            Volatility.EXTREME: "極高波動",
        }.get(volatility, "未知")
        
        pattern_text = f"，呈現{pattern.value}形態" if pattern != PatternType.NONE else ""
        
        return f"{trend_text}格局，{momentum_text}動能，{volatility_text}{pattern_text}"
