"""
決策控制器

整合 VSS 分析與人類判斷，輸出最終交易決策。
"""

from datetime import datetime
from typing import Optional, Callable

from vss.types import (
    HumanJudgment,
    VSSAnalysisResult,
    TrendDirection,
)
from vss.analyzer import VSSAnalyzer
from alignment.types import Decision, DecisionReason
from alignment.evaluator import AlignmentEvaluator
from alignment.recorder import JudgmentRecorder


class DecisionController:
    """
    決策控制器
    
    整合人類判斷與 VSS 分析，
    輸出最終交易決策。
    """
    
    def __init__(
        self,
        alignment_threshold: float = 0.7,
        confidence_threshold: float = 0.6,
        enable_recording: bool = True,
    ):
        """
        初始化控制器
        
        Args:
            alignment_threshold: 對齊閾值
            confidence_threshold: 信心度閾值
            enable_recording: 是否記錄決策
        """
        self.analyzer = VSSAnalyzer()
        self.evaluator = AlignmentEvaluator(
            alignment_threshold=alignment_threshold,
            confidence_threshold=confidence_threshold,
        )
        self.recorder = JudgmentRecorder() if enable_recording else None
        
        # 交易執行鉤子
        self._execute_callback: Optional[Callable] = None
    
    def set_execute_callback(self, callback: Callable):
        """設置交易執行回調"""
        self._execute_callback = callback
    
    def process(
        self,
        human_judgment: HumanJudgment,
        market_data,  # 可以是 DataFrame 或 VSSAnalysisResult
    ) -> dict:
        """
        處理決策流程
        
        Args:
            human_judgment: 人類判斷
            market_data: 市場數據 (DataFrame 或已有的 VSSAnalysisResult)
            
        Returns:
            決策結果字典
        """
        # Step 1: 獲取或計算 VSS 分析結果
        if isinstance(market_data, VSSAnalysisResult):
            vss_result = market_data
        else:
            vss_result = self.analyzer.analyze(
                df=market_data,
                symbol=human_judgment.symbol,
                interval=human_judgment.interval,
            )
        
        # Step 2: 評估對齊
        alignment_result = self.evaluator.evaluate(
            human_judgment=human_judgment,
            vss_result=vss_result,
        )
        
        # Step 3: 記錄
        if self.recorder:
            self.recorder.record_judgment(human_judgment)
            self.recorder.record_vss_result(vss_result)
            self.recorder.record_alignment(alignment_result)
        
        # Step 4: 生成決策
        decision = self._make_decision(alignment_result)
        
        # Step 5: 如果批准且有回調，執行交易
        if decision["action"] == Decision.APPROVE and self._execute_callback:
            try:
                execution_result = self._execute_callback(
                    symbol=human_judgment.symbol,
                    direction=human_judgment.trend,
                    vss_result=vss_result,
                    alignment=alignment_result,
                )
                decision["execution_result"] = execution_result
            except Exception as e:
                decision["execution_error"] = str(e)
        
        return decision
    
    def _make_decision(self, alignment_result) -> dict:
        """生成最終決策"""
        # 構建決策響應
        response = {
            "timestamp": datetime.now().isoformat(),
            "decision": alignment_result.can_execute,
            "action": Decision.APPROVE if alignment_result.can_execute else Decision.REJECT,
            "reason": alignment_result.reason,
            "alignment_score": alignment_result.alignment_score,
            "trend_match": alignment_result.trend_match,
            "human_judgment": alignment_result.human_judgment.to_dict(),
            "vss_result": alignment_result.vss_result.to_dict(),
            "difference_notes": alignment_result.difference_notes,
        }
        
        # 添加詳細建議
        if alignment_result.can_execute:
            response["suggestion"] = self._generate_suggestion(
                alignment_result.vss_result,
                alignment_result.human_judgment.trend,
            )
        else:
            response["suggestion"] = self._generate_rejection_suggestion(
                alignment_result,
            )
        
        return response
    
    def _generate_suggestion(
        self,
        vss_result: VSSAnalysisResult,
        direction: TrendDirection,
    ) -> dict:
        """生成執行建議"""
        market_state = vss_result.market_state
        
        # 進場時機建議
        suggestions = []
        
        # 根據趨勢給建議
        if direction == TrendDirection.UP:
            suggestions.append("建議現貨或合約做多")
            
            # 支撐位建議
            if market_state.nearest_support:
                suggestions.append(
                    f"支撐位參考: {market_state.nearest_support.level:.2f}"
                )
        else:
            suggestions.append("建議觀望或做空")
        
        # 風險建議
        suggestions.append(f"風險等級: {vss_result.risk_level}")
        
        if vss_result.risk_level == "medium":
            suggestions.append("建議縮小倉位")
        elif vss_result.risk_level == "high":
            suggestions.append("建議觀望")
        
        return {
            "direction": direction.value,
            "suggestions": suggestions,
            "market_state": market_state.description,
        }
    
    def _generate_rejection_suggestion(self, alignment_result) -> dict:
        """生成拒絕建議"""
        suggestions = []
        
        if not alignment_result.trend_match:
            suggestions.append("人類與 AI 趨勢判斷不一致，需要更多信息")
        
        if alignment_result.alignment_score < 0.7:
            suggestions.append(
                f"對齊分數過低 ({alignment_result.alignment_score:.0%})，"
                "建議等待更明確的信號"
            )
        
        if alignment_result.vss_result.risk_level == "high":
            suggestions.append("當前市場風險過高")
        
        if alignment_result.human_judgment.confidence < 0.6:
            suggestions.append("人類信心度不足")
        
        return {
            "action": "wait",
            "suggestions": suggestions,
            "monitor_again": True,
        }
    
    def get_statistics(self) -> dict:
        """獲取統計資訊"""
        if self.recorder:
            return self.recorder.get_statistics()
        return {}
    
    def analyze_misalignments(self) -> list:
        """分析不對齊案例"""
        if not self.recorder:
            return []
        
        misalignments = self.recorder.get_misalignment_cases()
        
        analysis = []
        for m in misalignments:
            analysis.append({
                "timestamp": m.timestamp.isoformat(),
                "symbol": m.human_judgment.symbol,
                "human_trend": m.human_judgment.trend.value,
                "vss_trend": m.vss_result.market_state.trend.value,
                "alignment_score": m.alignment_score,
                "difference": m.difference_notes,
            })
        
        return analysis
