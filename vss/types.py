"""
VSS 類型定義

定義市場狀態、分析結果等人機協作所需的資料結構。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class TrendDirection(Enum):
    """趨勢方向"""
    UP = "up"
    DOWN = "down"
    SIDEWAYS = "sideways"
    UNKNOWN = "unknown"


class PatternType(Enum):
    """技術圖形模式"""
    # 趨勢延續
    FLAG = "flag"              # 旗型
    PENNANT = "pennant"       # 楔形
    TRIANGLE_ASC = "triangle_ascending"   # 上升三角形
    TRIANGLE_DESC = "triangle_descending" # 下降三角形
    
    # 趨勢反轉
    HEAD_SHOULDERS = "head_and_shoulders"       # 頭肩頂
    HEAD_SHOULDERS_INV = "head_and_shoulders_inv" # 頭肩底
    DOUBLE_TOP = "double_top"      # 雙頂
    DOUBLE_BOTTOM = "double_bottom" # 雙底
    
    # 持續/盤整
    CHANNEL_UP = "channel_up"     # 上升通道
    CHANNEL_DOWN = "channel_down" # 下降通道
    RANGE = "range"              # 盤整區間
    WEDGE = "wedge"              # 楔形整理
    
    # 形態
    DOJI = "doji"                #十字線
    HAMMER = "hammer"            # 錘子線
    ENGULFING_BULL = "engulfing_bull"   # 多頭吞噬
    ENGULFING_BEAR = "engulfing_bear"   # 空頭吞噬
    
    NONE = "none"


class Momentum(Enum):
    """動能狀態"""
    STRONG_BULL = "strong_bull"
    MODERATE_BULL = "moderate_bull"
    NEUTRAL = "neutral"
    MODERATE_BEAR = "moderate_bear"
    STRONG_BEAR = "strong_bear"


class Volatility(Enum):
    """波動率狀態"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass
class SupportResistance:
    """支撐/壓力位"""
    level: float
    strength: float  # 0-1, 接觸次數越多越強
    type: str  # "support" or "resistance"


@dataclass
class MarketState:
    """市場狀態摘要"""
    timestamp: datetime
    
    # 趨勢
    trend: TrendDirection
    trend_confidence: float  # 0-1
    
    # 動能
    momentum: Momentum
    
    # 波動率
    volatility: Volatility
    
    # 價格位置
    current_price: float
    nearest_support: Optional[SupportResistance] = None
    nearest_resistance: Optional[SupportResistance] = None
    
    # 形態
    pattern: PatternType = PatternType.NONE
    pattern_confidence: float = 0.0
    
    # 成交量
    volume_status: str = "normal"  # "low", "normal", "high", "spike"
    
    # 額外描述
    description: str = ""
    
    def to_dict(self) -> dict:
        """轉換為字典"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "trend": self.trend.value,
            "trend_confidence": self.trend_confidence,
            "momentum": self.momentum.value,
            "volatility": self.volatility.value,
            "current_price": self.current_price,
            "pattern": self.pattern.value,
            "pattern_confidence": self.pattern_confidence,
            "volume_status": self.volume_status,
            "description": self.description,
        }


@dataclass
class VSSAnalysisResult:
    """VSS 分析結果"""
    timestamp: datetime
    symbol: str
    interval: str  # e.g., "1h", "4h", "1d"
    
    # 市場狀態
    market_state: MarketState
    
    # 原始分析資料
    price_change_pct: float  # 期間價格變化百分比
    volume_ratio: float     # 成交量相對平均
    
    # 分析細節
    indicators: dict = field(default_factory=dict)
    observations: list[str] = field(default_factory=list)
    
    # 風險評估
    risk_level: str = "medium"  # "low", "medium", "high"
    
    def to_dict(self) -> dict:
        """轉換為字典"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "interval": self.interval,
            "market_state": self.market_state.to_dict(),
            "price_change_pct": self.price_change_pct,
            "volume_ratio": self.volume_ratio,
            "indicators": self.indicators,
            "observations": self.observations,
            "risk_level": self.risk_level,
        }


@dataclass
class HumanJudgment:
    """人類判斷記錄"""
    timestamp: datetime
    
    # 標的資訊
    symbol: str
    interval: str
    
    # 人類觀點
    trend: TrendDirection
    confidence: float  # 0-1, 對自己判斷的信心程度
    
    # 額外觀察（可選）
    notes: str = ""
    pattern_observed: Optional[PatternType] = None
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "interval": self.interval,
            "trend": self.trend.value,
            "confidence": self.confidence,
            "notes": self.notes,
            "pattern_observed": self.pattern_observed.value if self.pattern_observed else None,
        }


@dataclass
class AlignmentResult:
    """對齊結果"""
    timestamp: datetime
    
    # 比較雙方的判斷
    human_judgment: HumanJudgment
    vss_result: VSSAnalysisResult
    
    # 對齊評估
    trend_match: bool
    alignment_score: float  # 0-1, 1 = 完全對齊
    
    # 差異分析
    difference_notes: str = ""
    
    # 决策
    can_execute: bool = False  # 是否可以執行交易
    reason: str = ""          # 原因說明
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "human_judgment": self.human_judgment.to_dict(),
            "vss_result": self.vss_result.to_dict(),
            "trend_match": self.trend_match,
            "alignment_score": self.alignment_score,
            "difference_notes": self.difference_notes,
            "can_execute": self.can_execute,
            "reason": self.reason,
        }


class Decision(Enum):
    """交易決策"""
    APPROVE = "approve"       # 批准執行
    REJECT = "reject"         # 拒絕執行
    WAIT = "wait"            # 等待更多信息
    REVIEW = "review"         # 需要人工覆審


class DecisionReason(Enum):
    """決策原因"""
    # 批准
    ALIGNED = "aligned"              # 人類與 VSS 對齊
    HIGH_CONFIDENCE = "high_confidence"  # 高信心度
    
    # 拒絕
    MISALIGNED = "misaligned"        # 人類與 VSS 不對齊
    LOW_CONFIDENCE = "low_confidence"  # 信心度不足
    HIGH_RISK = "high_risk"          # 高風險
    NO_TREND = "no_trend"            # 無明確趨勢
    
    # 等待/覆審
    CONFLICTING = "conflicting"      # 雙方判斷衝突
    UNCERTAIN = "uncertain"          # 不確定
