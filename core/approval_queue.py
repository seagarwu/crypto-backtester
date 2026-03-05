"""
Human Approval Queue - 人類審批系統

功能：
- 暫停交易等待人類批准
- 記錄審批歷史
- 支援多種審批方式（CLI、WebSocket、API）
"""

from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid
import threading
import time


class ApprovalStatus(Enum):
    """審批狀態"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ApprovalPriority(Enum):
    """審批優先級"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class ApprovalRequest:
    """審批請求"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    requester: str = ""  # 請求者（Agent 名稱）
    data: Dict[str, Any] = field(default_factory=dict)  # 請求的數據
    status: ApprovalStatus = ApprovalStatus.PENDING
    priority: ApprovalPriority = ApprovalPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    responded_at: Optional[datetime] = None
    responder: Optional[str] = None  # 審批者
    response_note: str = ""  # 審批備註
    
    # 審批條件（自動判斷）
    conditions: Dict[str, Any] = field(default_factory=dict)


class ApprovalRule:
    """審批規則"""
    
    def __init__(
        self,
        name: str,
        condition_fn: Callable[[Dict], bool],
        priority: ApprovalPriority = ApprovalPriority.NORMAL,
        description: str = "",
    ):
        self.name = name
        self.condition_fn = condition_fn
        self.priority = priority
        self.description = description
    
    def requires_approval(self, data: Dict[str, Any]) -> bool:
        """判斷是否需要審批"""
        try:
            return self.condition_fn(data)
        except Exception:
            return False


class HumanApprovalQueue:
    """
    人類審批隊列
    
    功能：
    - 接收審批請求
    - 維護待審批列表
    - 支援同步/異步審批
    - 自動審批規則
    """
    
    def __init__(self, timeout_seconds: float = 300):
        """
        初始化審批隊列
        
        Args:
            timeout_seconds: 審批超時時間（秒）
        """
        self.timeout_seconds = timeout_seconds
        self._pending: List[ApprovalRequest] = []
        self._history: List[ApprovalRequest] = []
        self._rules: List[ApprovalRule] = []
        self._lock = threading.RLock()
        
        # 回調
        self.on_approval_received: Optional[Callable] = None
        self.on_timeout: Optional[Callable] = None
        
        # 預設規則
        self._add_default_rules()
    
    def _add_default_rules(self):
        """添加默認規則"""
        
        # 金額大於 10000 需要審批
        self.add_rule(ApprovalRule(
            name="high_amount",
            condition_fn=lambda d: d.get("amount", 0) > 10000,
            priority=ApprovalPriority.HIGH,
            description="交易金額超過 $10,000",
        ))
        
        # 連續虧損 5 次需要審批
        self.add_rule(ApprovalRule(
            name="consecutive_losses",
            condition_fn=lambda d: d.get("consecutive_losses", 0) >= 5,
            priority=ApprovalPriority.URGENT,
            description="連續虧損 5 次以上",
        ))
        
        # 每日交易次數過多
        self.add_rule(ApprovalRule(
            name="high_frequency",
            condition_fn=lambda d: d.get("daily_trades", 0) > 20,
            priority=ApprovalPriority.HIGH,
            description="每日交易超過 20 次",
        ))
        
        # 總虧損過多
        self.add_rule(ApprovalRule(
            name="large_loss",
            condition_fn=lambda d: d.get("total_loss", 0) > 5000,
            priority=ApprovalPriority.URGENT,
            description="總虧損超過 $5,000",
        ))
    
    def add_rule(self, rule: ApprovalRule):
        """添加審批規則"""
        self._rules.append(rule)
        print(f"✅ 審批規則添加: {rule.name}")
    
    def remove_rule(self, name: str):
        """移除審批規則"""
        self._rules = [r for r in self._rules if r.name != name]
    
    def requires_approval(self, data: Dict[str, Any]) -> bool:
        """判斷數據是否需要人類審批"""
        for rule in self._rules:
            if rule.requires_approval(data):
                return True
        return False
    
    def get_required_rules(self, data: Dict[str, Any]) -> List[ApprovalRule]:
        """獲取需要審批的規則"""
        return [r for r in self._rules if r.requires_approval(data)]
    
    def request_approval(
        self,
        title: str,
        requester: str,
        data: Dict[str, Any] = None,
        description: str = "",
        priority: ApprovalPriority = None,
    ) -> ApprovalRequest:
        """
        請求人類審批
        
        Args:
            title: 請求標題
            requester: 請求者（Agent 名稱）
            data: 請求數據
            description: 詳細描述
            priority: 優先級（如果為 None，自動計算）
            
        Returns:
            ApprovalRequest 對象
        """
        # 自動計算優先級
        if priority is None:
            rules = self.get_required_rules(data or {})
            if any(r.priority == ApprovalPriority.URGENT for r in rules):
                priority = ApprovalPriority.URGENT
            elif any(r.priority == ApprovalPriority.HIGH for r in rules):
                priority = ApprovalPriority.HIGH
            else:
                priority = ApprovalPriority.NORMAL
        
        # 構建請求
        request = ApprovalRequest(
            title=title,
            description=description,
            requester=requester,
            data=data or {},
            priority=priority,
            conditions={"matched_rules": [r.name for r in self.get_required_rules(data or {})]},
        )
        
        with self._lock:
            self._pending.append(request)
            # 按優先級排序
            self._pending.sort(key=lambda x: x.priority.value, reverse=True)
        
        print(f"📋 審批請求: {title} (優先級: {priority.name})")
        
        return request
    
    def approve(
        self,
        request_id: str,
        responder: str = "human",
        note: str = "",
    ) -> bool:
        """
        批准請求
        
        Args:
            request_id: 請求 ID
            responder: 審批者
            note: 備註
            
        Returns:
            是否成功
        """
        with self._lock:
            for request in self._pending:
                if request.id == request_id:
                    request.status = ApprovalStatus.APPROVED
                    request.responder = responder
                    request.response_note = note
                    request.responded_at = datetime.now()
                    
                    # 移動到歷史
                    self._pending.remove(request)
                    self._history.append(request)
                    
                    print(f"✅ 審批通過: {request.title}")
                    
                    # 回調
                    if self.on_approval_received:
                        self.on_approval_received(request)
                    
                    return True
        
        return False
    
    def reject(
        self,
        request_id: str,
        responder: str = "human",
        note: str = "",
    ) -> bool:
        """
        拒絕請求
        
        Args:
            request_id: 請求 ID
            responder: 審批者
            note: 拒絕原因
            
        Returns:
            是否成功
        """
        with self._lock:
            for request in self._pending:
                if request.id == request_id:
                    request.status = ApprovalStatus.REJECTED
                    request.responder = responder
                    request.response_note = note
                    request.responded_at = datetime.now()
                    
                    # 移動到歷史
                    self._pending.remove(request)
                    self._history.append(request)
                    
                    print(f"❌ 審批拒絕: {request.title} - {note}")
                    
                    # 回調
                    if self.on_approval_received:
                        self.on_approval_received(request)
                    
                    return True
        
        return False
    
    def cancel(self, request_id: str) -> bool:
        """取消請求"""
        with self._lock:
            for request in self._pending:
                if request.id == request_id:
                    request.status = ApprovalStatus.CANCELLED
                    request.responded_at = datetime.now()
                    
                    self._pending.remove(request)
                    self._history.append(request)
                    
                    return True
        
        return False
    
    def get_pending(self) -> List[ApprovalRequest]:
        """獲取待審批列表"""
        with self._lock:
            return self._pending.copy()
    
    def get_by_id(self, request_id: str) -> Optional[ApprovalRequest]:
        """根據 ID 獲取請求"""
        with self._lock:
            for request in self._pending:
                if request.id == request_id:
                    return request
            for request in self._history:
                if request.id == request_id:
                    return request
        return None
    
    def wait_for_approval(
        self,
        request_id: str,
        timeout: float = None,
    ) -> ApprovalStatus:
        """
        同步等待審批結果
        
        Args:
            request_id: 請求 ID
            timeout: 超時時間
            
        Returns:
            最終狀態
        """
        if timeout is None:
            timeout = self.timeout_seconds
        
        start = time.time()
        
        while time.time() - start < timeout:
            request = self.get_by_id(request_id)
            
            if request is None:
                return ApprovalStatus.CANCELLED
            
            if request.status != ApprovalStatus.PENDING:
                return request.status
            
            time.sleep(0.5)
        
        # 超時
        with self._lock:
            for request in self._pending:
                if request.id == request_id:
                    request.status = ApprovalStatus.TIMEOUT
                    request.responded_at = datetime.now()
                    self._history.append(request)
                    
                    if self.on_timeout:
                        self.on_timeout(request)
                    
                    return ApprovalStatus.TIMEOUT
        
        return ApprovalStatus.TIMEOUT
    
    def get_history(self, limit: int = 100) -> List[ApprovalRequest]:
        """獲取審批歷史"""
        with self._lock:
            return self._history[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """獲取統計信息"""
        with self._lock:
            return {
                "pending": len(self._pending),
                "total_approved": sum(1 for r in self._history if r.status == ApprovalStatus.APPROVED),
                "total_rejected": sum(1 for r in self._history if r.status == ApprovalStatus.REJECTED),
                "total_timeout": sum(1 for r in self._history if r.status == ApprovalStatus.TIMEOUT),
                "rules_count": len(self._rules),
            }


# ==================== 便捷函數 ====================

_default_queue: Optional[HumanApprovalQueue] = None


def get_approval_queue() -> HumanApprovalQueue:
    """獲取默認審批隊列"""
    global _default_queue
    if _default_queue is None:
        _default_queue = HumanApprovalQueue()
    return _default_queue


def set_approval_queue(queue: HumanApprovalQueue) -> None:
    """設置默認審批隊列"""
    global _default_queue
    _default_queue = queue


def request_approval(
    title: str,
    requester: str,
    data: Dict[str, Any] = None,
    description: str = "",
) -> ApprovalRequest:
    """便捷請求審批"""
    return get_approval_queue().request_approval(title, requester, data, description)


def approve(request_id: str, note: str = "") -> bool:
    """便捷批准"""
    return get_approval_queue().approve(request_id, "human", note)


def reject(request_id: str, note: str = "") -> bool:
    """便捷拒絕"""
    return get_approval_queue().reject(request_id, "human", note)
