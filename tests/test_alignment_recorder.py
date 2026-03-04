"""
判斷記錄器測試

測試 JudgmentRecorder 的記錄與統計功能。
"""

import pytest
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from alignment.recorder import JudgmentRecorder
from alignment.types import Decision
from vss.types import (
    HumanJudgment,
    VSSAnalysisResult,
    MarketState,
    AlignmentResult,
    TrendDirection,
    PatternType,
    Momentum,
    Volatility,
)


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
) -> VSSAnalysisResult:
    return VSSAnalysisResult(
        timestamp=datetime.now(),
        symbol="BTCUSDT",
        interval="1h",
        market_state=create_market_state(trend, confidence),
        price_change_pct=5.0,
        volume_ratio=1.2,
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


def create_alignment_result(
    trend_match: bool = True,
    alignment_score: float = 0.8,
    can_execute: bool = True,
) -> AlignmentResult:
    human = create_human_judgment()
    vss = create_vss_result()
    
    return AlignmentResult(
        timestamp=datetime.now(),
        human_judgment=human,
        vss_result=vss,
        trend_match=trend_match,
        alignment_score=alignment_score,
        can_execute=can_execute,
        reason="Test reason",
    )


class TestJudgmentRecorderInit:
    """測試記錄器初始化"""
    
    def test_default_init(self):
        recorder = JudgmentRecorder()
        
        assert recorder.storage_dir == "data/judgments"
        assert isinstance(recorder.judgments, list)
        assert isinstance(recorder.vss_results, list)
        assert isinstance(recorder.alignments, list)
    
    def test_custom_init(self):
        recorder = JudgmentRecorder(storage_dir="/tmp/test_judgments")
        
        assert recorder.storage_dir == "/tmp/test_judgments"


class TestJudgmentRecorderRecording:
    """測試記錄功能"""
    
    def test_record_judgment(self):
        recorder = JudgmentRecorder()
        judgment = create_human_judgment()
        
        recorder.record_judgment(judgment)
        
        assert len(recorder.judgments) == 1
        assert recorder.judgments[0] == judgment
    
    def test_record_multiple_judgments(self):
        recorder = JudgmentRecorder()
        
        recorder.record_judgment(create_human_judgment(TrendDirection.UP))
        recorder.record_judgment(create_human_judgment(TrendDirection.DOWN))
        recorder.record_judgment(create_human_judgment(TrendDirection.SIDEWAYS))
        
        assert len(recorder.judgments) == 3
    
    def test_record_vss_result(self):
        recorder = JudgmentRecorder()
        vss_result = create_vss_result()
        
        recorder.record_vss_result(vss_result)
        
        assert len(recorder.vss_results) == 1
    
    def test_record_alignment(self):
        recorder = JudgmentRecorder()
        alignment = create_alignment_result()
        
        recorder.record_alignment(alignment)
        
        assert len(recorder.alignments) == 1
    
    def test_record_mixed(self):
        """記錄混合數據"""
        recorder = JudgmentRecorder()
        
        judgment = create_human_judgment()
        vss = create_vss_result()
        alignment = create_alignment_result()
        
        recorder.record_judgment(judgment)
        recorder.record_vss_result(vss)
        recorder.record_alignment(alignment)
        
        assert len(recorder.judgments) == 1
        assert len(recorder.vss_results) == 1
        assert len(recorder.alignments) == 1


class TestJudgmentRecorderStatistics:
    """測試統計功能"""
    
    def test_get_statistics_empty(self):
        recorder = JudgmentRecorder()
        
        stats = recorder.get_statistics()
        
        assert stats['total_decisions'] == 0
        assert stats['approved'] == 0
        assert stats['rejected'] == 0
        assert stats['approval_rate'] == 0
    
    def test_get_statistics_all_approved(self):
        recorder = JudgmentRecorder()
        
        # 記錄 3 個批准
        for _ in range(3):
            recorder.record_alignment(create_alignment_result(
                trend_match=True,
                alignment_score=0.8,
                can_execute=True,
            ))
        
        stats = recorder.get_statistics()
        
        assert stats['total_decisions'] == 3
        assert stats['approved'] == 3
        assert stats['rejected'] == 0
        assert stats['approval_rate'] == 1.0
    
    def test_get_statistics_all_rejected(self):
        recorder = JudgmentRecorder()
        
        # 記錄 2 個拒絕
        for _ in range(2):
            recorder.record_alignment(create_alignment_result(
                trend_match=False,
                alignment_score=0.2,
                can_execute=False,
            ))
        
        stats = recorder.get_statistics()
        
        assert stats['total_decisions'] == 2
        assert stats['approved'] == 0
        assert stats['rejected'] == 2
        assert stats['approval_rate'] == 0.0
    
    def test_get_statistics_mixed(self):
        recorder = JudgmentRecorder()
        
        recorder.record_alignment(create_alignment_result(can_execute=True))
        recorder.record_alignment(create_alignment_result(can_execute=True))
        recorder.record_alignment(create_alignment_result(can_execute=False))
        
        stats = recorder.get_statistics()
        
        assert stats['total_decisions'] == 3
        assert stats['approved'] == 2
        assert stats['rejected'] == 1
        assert stats['approval_rate'] == pytest.approx(2/3)
    
    def test_get_statistics_by_symbol(self):
        recorder = JudgmentRecorder()
        
        # BTC 2 次
        recorder.record_alignment(create_alignment_result())
        recorder.record_alignment(create_alignment_result())
        
        # ETH 1 次
        human_eth = HumanJudgment(
            timestamp=datetime.now(),
            symbol="ETHUSDT",
            interval="1h",
            trend=TrendDirection.UP,
            confidence=0.75,
        )
        vss_eth = create_vss_result()
        alignment_eth = AlignmentResult(
            timestamp=datetime.now(),
            human_judgment=human_eth,
            vss_result=vss_eth,
            trend_match=True,
            alignment_score=0.8,
            can_execute=True,
            reason="Test",
        )
        recorder.record_alignment(alignment_eth)
        
        stats = recorder.get_statistics()
        
        assert 'by_symbol' in stats
        assert stats['by_symbol']['BTCUSDT'] == 2
        assert stats['by_symbol']['ETHUSDT'] == 1


class TestJudgmentRecorderMisalignments:
    """測試不對齊案例查詢"""
    
    def test_get_misalignment_cases_empty(self):
        recorder = JudgmentRecorder()
        
        cases = recorder.get_misalignment_cases()
        
        assert len(cases) == 0
    
    def test_get_misalignment_cases_with_data(self):
        recorder = JudgmentRecorder()
        
        # 記錄對齊的
        recorder.record_alignment(create_alignment_result(
            trend_match=True,
            alignment_score=0.9,
            can_execute=True,
        ))
        
        # 記錄不對齊的
        recorder.record_alignment(create_alignment_result(
            trend_match=False,
            alignment_score=0.5,
            can_execute=False,
        ))
        
        cases = recorder.get_misalignment_cases()
        
        assert len(cases) == 1
    
    def test_get_misalignment_cases_threshold(self):
        recorder = JudgmentRecorder()
        
        # 記錄多個不對齊案例
        recorder.record_alignment(create_alignment_result(
            trend_match=False,
            alignment_score=0.3,
            can_execute=False,
        ))
        recorder.record_alignment(create_alignment_result(
            trend_match=False,
            alignment_score=0.4,
            can_execute=False,
        ))
        recorder.record_alignment(create_alignment_result(
            trend_match=True,
            alignment_score=0.8,
            can_execute=True,
        ))
        
        # 使用閾值過濾 - 獲取分數低於閾值的
        cases = recorder.get_misalignment_cases(score_threshold=0.4)
        
        assert len(cases) == 2  # 0.3 和 0.4 都低於 0.4


class TestJudgmentRecorderPersistence:
    """測試持久化功能"""
    
    def test_save_to_file(self, tmp_path):
        recorder = JudgmentRecorder(storage_dir=str(tmp_path))
        
        recorder.record_judgment(create_human_judgment())
        
        recorder.save()
        
        # 檢查文件是否存在
        judgment_file = tmp_path / "judgments.json"
        assert judgment_file.exists()
    
    def test_load_from_file(self, tmp_path):
        recorder = JudgmentRecorder(storage_dir=str(tmp_path))
        
        # 先記錄並保存
        judgment = create_human_judgment()
        recorder.record_judgment(judgment)
        recorder.save()
        
        # 創建新的 recorder 並加載
        new_recorder = JudgmentRecorder.load(str(tmp_path))
        
        assert len(new_recorder.judgments) >= 1
    
    def test_save_empty_recorder(self, tmp_path):
        """空記錄器應該也能保存"""
        recorder = JudgmentRecorder(storage_dir=str(tmp_path))
        
        # 不應該崩潰
        recorder.save()
    
    def test_load_nonexistent_file(self):
        """加載不存在的文件應該安全處理"""
        # 不應該崩潰
        recorder = JudgmentRecorder.load("/nonexistent/path")
        assert recorder is not None


class TestJudgmentRecorderFiltering:
    """測試篩選功能"""
    
    def test_filter_by_symbol(self):
        recorder = JudgmentRecorder()
        
        # BTC
        recorder.record_judgment(create_human_judgment())
        # ETH
        judgment_eth = HumanJudgment(
            timestamp=datetime.now(),
            symbol="ETHUSDT",
            interval="1h",
            trend=TrendDirection.UP,
            confidence=0.75,
        )
        recorder.record_judgment(judgment_eth)
        
        btc_judgments = recorder.filter_judgments(symbol="BTCUSDT")
        
        assert len(btc_judgments) == 1
        assert btc_judgments[0].symbol == "BTCUSDT"
    
    def test_filter_by_trend(self):
        recorder = JudgmentRecorder()
        
        recorder.record_judgment(create_human_judgment(TrendDirection.UP))
        recorder.record_judgment(create_human_judgment(TrendDirection.DOWN))
        
        up_judgments = recorder.filter_judgments(trend=TrendDirection.UP)
        
        assert len(up_judgments) == 1
        assert up_judgments[0].trend == TrendDirection.UP
    
    def test_filter_by_date_range(self):
        recorder = JudgmentRecorder()
        
        # 舊的記錄
        old_judgment = create_human_judgment()
        old_judgment.timestamp = datetime.now() - timedelta(days=10)
        recorder.record_judgment(old_judgment)
        
        # 新的記錄
        new_judgment = create_human_judgment()
        new_judgment.timestamp = datetime.now()
        recorder.record_judgment(new_judgment)
        
        # 篩選最近 5 天
        recent = recorder.filter_judgments(
            start_date=datetime.now() - timedelta(days=5)
        )
        
        assert len(recent) == 1


class TestJudgmentRecorderAlignmentAnalysis:
    """測試對齊分析功能"""
    
    def test_get_alignment_trend(self):
        recorder = JudgmentRecorder()
        
        # 記錄一系列對齊結果
        for score in [0.9, 0.8, 0.7, 0.6, 0.5]:
            recorder.record_alignment(create_alignment_result(
                alignment_score=score,
                trend_match=score > 0.65,
            ))
        
        trend = recorder.get_alignment_trend()
        
        # 應該顯示下降趨勢
        assert trend in ['improving', 'declining', 'stable']
    
    def test_get_average_alignment(self):
        recorder = JudgmentRecorder()
        
        for score in [0.9, 0.7, 0.5]:
            recorder.record_alignment(create_alignment_result(
                alignment_score=score,
            ))
        
        avg = recorder.get_average_alignment()
        
        assert avg == pytest.approx(0.7, rel=0.01)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
