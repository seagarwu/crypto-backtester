"""
對齊評估器

比較人類判斷與 VSS 分析結果，計算對齊分數。
"""

from datetime import datetime
from typing import Optional

from vss.types import (
    AlignmentResult,
    HumanJudgment,
    VSSAnalysisResult,
    TrendDirection,
    MarketState,
)
from .types import Decision, DecisionReason


class AlignmentEvaluator:
    """
    對齊評估器
    
    比較人類與 VSS 的市場判斷，計算對齊程度。
    """
    
    def __init__(
        self,
        alignment_threshold: float = 0.7,
        confidence_threshold: float = 0.6,
    ):
        """
        初始化評估器
        
        Args:
            alignment_threshold: 對齊閾值，高於此值視為對齊
            confidence_threshold: 信心度閾值
        """
        self.alignment_threshold = alignment_threshold
        self.confidence_threshold = confidence_threshold
    
    def evaluate(
        self,
        human_judgment: HumanJudgment,
        vss_result: VSSAnalysisResult,
    ) -> AlignmentResult:
        """
        評估對齊程度
        
        Args:
            human_judgment: 人類判斷
            vss_result: VSS 分析結果
            
        Returns:
            AlignmentResult: 對齊結果
        """
        # 趨勢是否匹配
        human_trend = human_judgment.trend
        vss_trend = vss_result.market_state.trend
        trend_match = human_trend == vss_trend
        
        # 計算對齊分數
        alignment_score = self._calculate_alignment_score(
            human_judgment,
            vss_result,
        )
        
        # 差異分析
        difference_notes = self._analyze_differences(
            human_judgment,
            vss_result,
        )
        
        # 決策判斷
        can_execute, reason = self._determine_decision(
            trend_match=trend_match,
            alignment_score=alignment_score,
            human_confidence=human_judgment.confidence,
            vss_confidence=vss_result.market_state.trend_confidence,
            risk_level=vss_result.risk_level,
            vss_trend=vss_trend,
        )
        
        return AlignmentResult(
            timestamp=datetime.now(),
            human_judgment=human_judgment,
            vss_result=vss_result,
            trend_match=trend_match,
            alignment_score=alignment_score,
            difference_notes=difference_notes,
            can_execute=can_execute,
            reason=reason,
        )
    
    def _calculate_alignment_score(
        self,
        human_judgment: HumanJudgment,
        vss_result: VSSAnalysisResult,
    ) -> float:
        """
        計算對齊分數
        
        考慮因素：
        1. 趨勢是否一致
        2. 雙方信心度
        3. 形態識別是否一致
        """
        score = 0.0
        weights = 0.0
        
        # 趨勢權重 60%
        weights += 0.6
        if human_judgment.trend == vss_result.market_state.trend:
            # 完全一致
            score += 0.6
        elif human_judgment.trend != TrendDirection.UNKNOWN and \
             vss_result.market_state.trend != TrendDirection.UNKNOWN:
            # 不一致但都明確
            score += 0.1
        # 否則為 0
        
        # 信心度權重 20%
        weights += 0.2
        # 取雙方信心度的平均
        avg_confidence = (human_judgment.confidence + 
                         vss_result.market_state.trend_confidence) / 2
        score += avg_confidence * 0.2
        
        # 形態權重 20%
        weights += 0.2
        if human_judgment.pattern_observed and \
           human_judgment.pattern_observed == vss_result.market_state.pattern:
            score += 0.2
        elif not human_judgment.pattern_observed:
            # 人類沒有特別觀察形態，給予部分分數
            score += 0.1
        
        return min(score / weights, 1.0)
    
    def _analyze_differences(
        self,
        human_judgment: HumanJudgment,
        vss_result: VSSAnalysisResult,
    ) -> str:
        """分析雙方判斷差異"""
        notes = []
        
        # 趨勢差異
        if human_judgment.trend != vss_result.market_state.trend:
            notes.append(
                f"趨勢判斷不同: 人類({human_judgment.trend.value}) vs "
                f"VSS({vss_result.market_state.trend.value})"
            )
        
        # 信心度差異
        conf_diff = abs(human_judgment.confidence - 
                       vss_result.market_state.trend_confidence)
        if conf_diff > 0.3:
            notes.append(
                f"信心度差異大: 人類({human_judgment.confidence:.0%}) vs "
                f"VSS({vss_result.market_state.trend_confidence:.0%})"
            )
        
        # 形態差異
        if human_judgment.pattern_observed and \
           human_judgment.pattern_observed != vss_result.market_state.pattern:
            notes.append(
                f"形態識別不同: 人類({human_judgment.pattern_observed.value}) vs "
                f"VSS({vss_result.market_state.pattern.value})"
            )
        
        return "; ".join(notes) if notes else "雙方判斷基本一致"
    
    def _determine_decision(
        self,
        trend_match: bool,
        alignment_score: float,
        human_confidence: float,
        vss_confidence: float,
        risk_level: str,
        vss_trend: TrendDirection,
    ) -> tuple[bool, str]:
        """
        判斷是否可以執行交易
        
        Returns:
            (can_execute, reason)
        """
        # 風險過高，拒絕
        if risk_level == "high":
            return False, f"風險過高 ({risk_level})"
        
        # 無明確趨勢，拒絕
        if vss_trend == TrendDirection.UNKNOWN:
            return False, "VSS 無法判斷趨勢"
        
        # 完全對齊且信心足夠
        if alignment_score >= self.alignment_threshold and \
           human_confidence >= self.confidence_threshold and \
           vss_confidence >= self.confidence_threshold and \
           trend_match:
            return True, f"對齊良好 (分數: {alignment_score:.0%})"
        
        # 對齊但信心不足
        if alignment_score >= self.alignment_threshold:
            if human_confidence < self.confidence_threshold:
                return False, "人類信心度不足"
            if vss_confidence < self.confidence_threshold:
                return False, "VSS 信心度不足"
        
        # 不對齊
        if not trend_match:
            return False, f"趨勢不對齊 (分數: {alignment_score:.0%})"
        
        # 其他情況
        if alignment_score < self.alignment_threshold:
            return False, f"對齊分數不足 ({alignment_score:.0%})"
        
        return False, "不符合執行條件"
    
    def batch_evaluate(
        self,
        judgments: list[HumanJudgment],
        vss_results: list[VSSAnalysisResult],
    ) -> list[AlignmentResult]:
        """
        批量評估
        
        假設 judgments 和 vss_results 按時間順序對應
        """
        results = []
        
        for judgment, vss_result in zip(judgments, vss_results):
            result = self.evaluate(judgment, vss_result)
            results.append(result)
        
        return results
