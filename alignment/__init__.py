"""
人機對齊模組

負責人類判斷與 VSS 分析結果的對齊評估與決策控制。
"""

from vss.types import (
    AlignmentResult,
    HumanJudgment,
    VSSAnalysisResult,
)
from .types import (
    Decision,
    DecisionReason,
)
from .evaluator import AlignmentEvaluator
from .recorder import JudgmentRecorder
from .controller import DecisionController

__all__ = [
    "AlignmentResult",
    "Decision",
    "DecisionReason",
    "AlignmentEvaluator",
    "JudgmentRecorder",
    "DecisionController",
]
