"""
對齊模組類型定義
"""

from enum import Enum


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
