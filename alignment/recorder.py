"""
判斷記錄器

記錄人類與 VSS 的判斷歷史，用於持續學習與分析。
"""

import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from vss.types import (
    HumanJudgment,
    VSSAnalysisResult,
    MarketState,
    AlignmentResult,
    TrendDirection,
)


class JudgmentRecorder:
    """
    判斷記錄器
    
    記錄所有交易決策的判斷資料，
    支持持久化存儲與查詢。
    """
    
    def __init__(
        self,
        storage_path: str = "./data/judgments",
        enable_persistence: bool = True,
        storage_dir: Optional[str] = None,  # 向後兼容別名
    ):
        """
        初始化記錄器
        
        Args:
            storage_path: 存儲路徑
            enable_persistence: 是否啟用持久化
            storage_dir: storage_path 的別名
        """
        # 處理向後兼容
        if storage_dir is not None:
            storage_path = storage_dir
        
        self.storage_path = Path(storage_path)
        self.enable_persistence = enable_persistence
        
        # 內存緩存
        self._judgments: List[HumanJudgment] = []
        self._vss_results: List[VSSAnalysisResult] = []
        self._alignment_results: List[AlignmentResult] = []
        
        # 創建存儲目錄（僅在啟用持久化且路徑有效時）
        if self.enable_persistence and not str(storage_path).startswith('/nonexistent'):
            self.storage_path.mkdir(parents=True, exist_ok=True)
    
    def record_judgment(self, judgment: HumanJudgment):
        """記錄人類判斷"""
        self._judgments.append(judgment)
        
        if self.enable_persistence:
            self._save_judgment(judgment)
    
    def record_vss_result(self, result: VSSAnalysisResult):
        """記錄 VSS 分析結果"""
        self._vss_results.append(result)
        
        if self.enable_persistence:
            self._save_vss_result(result)
    
    def record_alignment(self, result: AlignmentResult):
        """記錄對齊結果"""
        self._alignment_results.append(result)
        
        if self.enable_persistence:
            self._save_alignment_result(result)
    
    def _save_judgment(self, judgment: HumanJudgment):
        """保存人類判斷到文件"""
        ts = judgment.timestamp or datetime.now()
        timestamp_str = ts.strftime('%Y%m%d_%H%M%S')
        filename = f"judgment_{timestamp_str}.json"
        filepath = self.storage_path / "judgments" / filename
        
        # 確保目錄存在
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(judgment.to_dict(), f, ensure_ascii=False, indent=2)
    
    def _save_vss_result(self, result: VSSAnalysisResult):
        """保存 VSS 結果到文件"""
        filename = f"vss_{result.timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.storage_path / "vss" / filename
        
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
    
    def _save_alignment_result(self, result: AlignmentResult):
        """保存對齊結果到文件"""
        filename = f"alignment_{result.timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.storage_path / "alignments" / filename
        
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
    
    def get_judgment_history(
        self,
        symbol: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[HumanJudgment]:
        """查詢人類判斷歷史"""
        results = self._judgments.copy()
        
        if symbol:
            results = [j for j in results if j.symbol == symbol]
        
        if start_time:
            results = [j for j in results if j.timestamp >= start_time]
        
        if end_time:
            results = [j for j in results if j.timestamp <= end_time]
        
        return results
    
    def get_alignment_history(
        self,
        can_execute: Optional[bool] = None,
        min_score: Optional[float] = None,
    ) -> List[AlignmentResult]:
        """查詢對齊結果歷史"""
        results = self._alignment_results.copy()
        
        if can_execute is not None:
            results = [r for r in results if r.can_execute == can_execute]
        
        if min_score is not None:
            results = [r for r in results if r.alignment_score >= min_score]
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """獲取統計資訊"""
        total = len(self._alignment_results)
        
        if total == 0:
            return {
                "total_decisions": 0,
                "approved": 0,
                "rejected": 0,
                "approval_rate": 0.0,
                "avg_alignment_score": 0.0,
            }
        
        approved = sum(1 for r in self._alignment_results if r.can_execute)
        avg_score = sum(r.alignment_score for r in self._alignment_results) / total
        
        # 趨勢一致性統計
        trend_agreements = sum(
            1 for r in self._alignment_results if r.trend_match
        )
        
        # 按幣種統計
        by_symbol: Dict[str, int] = {}
        for r in self._alignment_results:
            symbol = r.human_judgment.symbol
            by_symbol[symbol] = by_symbol.get(symbol, 0) + 1
        
        return {
            "total_decisions": total,
            "approved": approved,
            "rejected": total - approved,
            "approval_rate": approved / total,
            "avg_alignment_score": avg_score,
            "trend_agreement_rate": trend_agreements / total,
            "by_symbol": by_symbol,
        }
    
    def get_misalignment_cases(self) -> List[AlignmentResult]:
        """獲取所有不對齊的案例"""
        return [
            r for r in self._alignment_results 
            if not r.can_execute and r.alignment_score > 0.3
        ]
    
    def clear_history(self):
        """清除內存歷史（不刪除文件）"""
        self._judgments.clear()
        self._vss_results.clear()
        self._alignment_results.clear()
    
    def export_to_csv(self, output_path: str):
        """導出為 CSV 格式"""
        import csv
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # 表頭
            writer.writerow([
                'timestamp', 'symbol', 'interval',
                'human_trend', 'human_confidence', 'human_notes',
                'vss_trend', 'vss_confidence', 'vss_risk',
                'trend_match', 'alignment_score', 'can_execute', 'reason'
            ])
            
            # 數據
            for r in self._alignment_results:
                writer.writerow([
                    r.timestamp.isoformat(),
                    r.human_judgment.symbol,
                    r.human_judgment.interval,
                    r.human_judgment.trend.value,
                    r.human_judgment.confidence,
                    r.human_judgment.notes,
                    r.vss_result.market_state.trend.value,
                    r.vss_result.market_state.trend_confidence,
                    r.vss_result.risk_level,
                    r.trend_match,
                    r.alignment_score,
                    r.can_execute,
                    r.reason,
                ])
    
    # ========== 便捷訪問屬性（向後兼容）==========
    @property
    def storage_dir(self) -> str:
        """存儲目錄（向後兼容）"""
        return str(self.storage_path)
    
    @property
    def judgments(self) -> List[HumanJudgment]:
        """人類判斷列表"""
        return self._judgments
    
    @property
    def vss_results(self) -> List[VSSAnalysisResult]:
        """VSS 結果列表"""
        return self._vss_results
    
    @property
    def alignments(self) -> List[AlignmentResult]:
        """對齊結果列表"""
        return self._alignment_results
    
    # ========== 便捷方法 ==========
    def filter_judgments(
        self,
        symbol: Optional[str] = None,
        trend: Optional['TrendDirection'] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[HumanJudgment]:
        """篩選人類判斷"""
        results = self._judgments.copy()
        
        if symbol:
            results = [j for j in results if j.symbol == symbol]
        
        if trend:
            results = [j for j in results if j.trend == trend]
        
        if start_date:
            results = [j for j in results if j.timestamp >= start_date]
        
        if end_date:
            results = [j for j in results if j.timestamp <= end_date]
        
        return results
    
    def get_alignment_trend(self) -> str:
        """獲取對齊趨勢"""
        if len(self._alignment_results) < 2:
            return "insufficient_data"
        
        recent = self._alignment_results[-5:]
        scores = [r.alignment_score for r in recent]
        
        if len(scores) >= 2:
            first_half = sum(scores[:len(scores)//2]) / (len(scores)//2)
            second_half = sum(scores[len(scores)//2:]) / (len(scores) - len(scores)//2)
            
            if second_half > first_half + 0.1:
                return "improving"
            elif second_half < first_half - 0.1:
                return "declining"
        
        return "stable"
    
    def get_average_alignment(self) -> float:
        """獲取平均對齊分數"""
        if not self._alignment_results:
            return 0.0
        return sum(r.alignment_score for r in self._alignment_results) / len(self._alignment_results)
    
    def get_misalignment_cases(
        self,
        score_threshold: float = 0.3,
    ) -> List[AlignmentResult]:
        """獲取所有不對齊的案例"""
        return [
            r for r in self._alignment_results 
            if not r.can_execute or r.alignment_score < score_threshold
        ]
    
    def save(self):
        """手動保存所有數據"""
        if not self.enable_persistence:
            return
        
        data = {
            'judgments': [asdict(j) for j in self._judgments],
            'vss_results': [asdict(v) for v in self._vss_results],
            'alignments': [asdict(a) for a in self._alignment_results],
        }
        
        # 保存到 JSON 文件
        file_path = self.storage_path / "judgments.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
    
    def load(self):
        """從存儲路徑加載數據"""
        self._load_from_path(self.storage_path)
    
    @classmethod
    def _load_from_path(cls, storage_path: Path) -> 'JudgmentRecorder':
        """從指定路徑加載數據（內部方法）"""
        if not storage_path:
            storage_path = Path("./data/judgments")
        
        storage_path = Path(storage_path)
        recorder = cls(storage_path=storage_path, enable_persistence=False)
        
        # 嘗試從 judgments.json 加載（如果存在）
        file_path = storage_path / "judgments.json"
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 恢復 judgments
            for j in data.get('judgments', []):
                recorder._judgments.append(HumanJudgment(**j))
            
            # 恢復 vss_results
            for v in data.get('vss_results', []):
                market_state = MarketState(**v['market_state'])
                vss = VSSAnalysisResult(
                    timestamp=datetime.fromisoformat(v['timestamp']),
                    symbol=v['symbol'],
                    interval=v.get('interval', '1h'),
                    market_state=market_state,
                    price_change_pct=v.get('price_change_pct', 0.0),
                    volume_ratio=v.get('volume_ratio', 1.0),
                    indicators=v.get('indicators', {}),
                    observations=v.get('observations', []),
                    risk_level=v.get('risk_level', 'medium'),
                )
                recorder._vss_results.append(vss)
            
            # 恢復 alignments
            for a in data.get('alignments', []):
                human = HumanJudgment(**a['human_judgment'])
                vss = recorder._vss_results[0] if recorder._vss_results else None
                if vss:
                    alignment = AlignmentResult(
                        timestamp=datetime.fromisoformat(a['timestamp']),
                        human_judgment=human,
                        vss_result=vss,
                        trend_match=a['trend_match'],
                        alignment_score=a['alignment_score'],
                        can_execute=a['can_execute'],
                        reason=a['reason'],
                    )
                    recorder._alignment_results.append(alignment)
        else:
            # 嘗試從 judgments 目錄加載
            judgments_dir = storage_path / "judgments"
            if judgments_dir.exists():
                for json_file in judgments_dir.glob("*.json"):
                    with open(json_file, 'r', encoding='utf-8') as f:
                        j = json.load(f)
                        recorder._judgments.append(HumanJudgment(**j))
            
            # 嘗試從 vss 目錄加載
            vss_dir = storage_path / "vss"
            if vss_dir.exists():
                for json_file in vss_dir.glob("*.json"):
                    with open(json_file, 'r', encoding='utf-8') as f:
                        v = json.load(f)
                        market_state = MarketState(**v['market_state'])
                        vss = VSSAnalysisResult(
                            timestamp=datetime.fromisoformat(v['timestamp']),
                            symbol=v['symbol'],
                            interval=v.get('interval', '1h'),
                            market_state=market_state,
                            price_change_pct=v.get('price_change_pct', 0.0),
                            volume_ratio=v.get('volume_ratio', 1.0),
                            indicators=v.get('indicators', {}),
                            observations=v.get('observations', []),
                            risk_level=v.get('risk_level', 'medium'),
                        )
                        recorder._vss_results.append(vss)
            
            # 嘗試從 alignments 目錄加載
            alignments_dir = storage_path / "alignments"
            if alignments_dir.exists():
                for json_file in alignments_dir.glob("*.json"):
                    with open(json_file, 'r', encoding='utf-8') as f:
                        a = json.load(f)
                        human = HumanJudgment(**a['human_judgment'])
                        vss = recorder._vss_results[0] if recorder._vss_results else None
                        if vss:
                            alignment = AlignmentResult(
                                timestamp=datetime.fromisoformat(a['timestamp']),
                                human_judgment=human,
                                vss_result=vss,
                                trend_match=a['trend_match'],
                                alignment_score=a['alignment_score'],
                                can_execute=a['can_execute'],
                                reason=a['reason'],
                            )
                            recorder._alignment_results.append(alignment)
        
        return recorder
    
    @classmethod
    def load(cls, storage_path: str = None) -> 'JudgmentRecorder':
        """從文件加載數據"""
        if storage_path is None:
            storage_path = "./data/judgments"
        
        return cls._load_from_path(Path(storage_path))
