"""
Message Bus - 事件驅動訊息總線

提供發布/訂閱機制，讓 Agents 可以透過事件進行通訊。
"""

from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading
import json
import uuid


class EventType(Enum):
    """事件類型"""
    # Market Events
    NEW_MARKET_DATA = "new_market_data"
    PRICE_ALERT = "price_alert"
    VOLATILITY_ALERT = "volatility_alert"
    
    # Trading Events
    SIGNAL_GENERATED = "signal_generated"
    RISK_ASSESSMENT = "risk_assessment"
    TRADE_EXECUTED = "trade_executed"
    TRADE_REJECTED = "trade_rejected"
    
    # Human Events
    HUMAN_APPROVAL_REQUEST = "human_approval_request"
    HUMAN_APPROVAL_RECEIVED = "human_approval_received"
    HUMAN_FEEDBACK = "human_feedback"
    
    # System Events
    AGENT_REGISTERED = "agent_registered"
    AGENT_UNREGISTERED = "agent_unregistered"
    SYSTEM_ERROR = "system_error"
    SYSTEM_STATUS = "system_status"


@dataclass
class Event:
    """事件"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: EventType = EventType.SYSTEM_STATUS
    source: str = ""
    target: Optional[str] = None  # 特定 Agent 或 None (廣播)
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    correlation_id: Optional[str] = None  # 用於追蹤相關事件
    metadata: Dict[str, Any] = field(default_factory=dict)


class MessageBus:
    """
    訊息總線 - 事件驅動核心
    
    支援：
    - 發布/訂閱
    - 廣播或特定目標
    - 事件歷史
    - 同步/異步處理
    """
    
    def __init__(self, history_size: int = 1000):
        """
        初始化訊息總線
        
        Args:
            history_size: 歷史事件儲存數量
        """
        self._subscribers: Dict[EventType, List[Callable]] = {}
        self._event_history: List[Event] = []
        self._history_size = history_size
        self._lock = threading.RLock()
        
        # 統計
        self._event_count: Dict[EventType, int] = {}
    
    def subscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], None],
        agent_name: str = None,
    ) -> None:
        """
        訂閱事件
        
        Args:
            event_type: 事件類型
            handler: 處理函數 (event: Event) -> None
            agent_name: 訂閱者名稱（可選，用於日誌）
        """
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            
            # 包裝 handler，添加日誌
            def wrapped_handler(event: Event):
                agent = agent_name or "unknown"
                print(f"📬 [{agent}] 收到事件: {event.type.value}")
                try:
                    handler(event)
                except Exception as e:
                    print(f"❌ [{agent}] 處理事件失敗: {e}")
            
            self._subscribers[event_type].append(wrapped_handler)
            print(f"✅ 訂閱: {event_type.value} <- {agent_name or 'anonymous'}")
    
    def unsubscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], None],
    ) -> None:
        """取消訂閱"""
        with self._lock:
            if event_type in self._subscribers:
                self._subscribers[event_type].remove(handler)
    
    def publish(self, event: Event) -> None:
        """
        發布事件
        
        Args:
            event: 事件對象
        """
        with self._lock:
            # 記錄歷史
            self._event_history.append(event)
            if len(self._event_history) > self._history_size:
                self._event_history = self._event_history[-self._history_size:]
            
            # 統計
            self._event_count[event.type] = self._event_count.get(event.type, 0) + 1
            
            # 打印日誌
            print(f"📢 發布事件: {event.type.value} (from: {event.source})")
        
        # 觸發處理器（在 lock 外，避免死鎖）
        handlers = []
        with self._lock:
            if event.type in self._subscribers:
                handlers = self._subscribers[event.type].copy()
        
        # 廣播給所有訂閱者
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                print(f"❌ 處理器執行失敗: {e}")
    
    def publish_sync(
        self,
        event_type: EventType,
        source: str,
        data: Dict[str, Any] = None,
        target: str = None,
    ) -> Event:
        """
        同步發布（便捷方法）
        
        Args:
            event_type: 事件類型
            source: 來源 Agent
            data: 事件數據
            target: 目標 Agent（可選）
            
        Returns:
            發布的事件對象
        """
        event = Event(
            type=event_type,
            source=source,
            target=target,
            data=data or {},
        )
        self.publish(event)
        return event
    
    def get_history(
        self,
        event_type: EventType = None,
        source: str = None,
        limit: int = 100,
    ) -> List[Event]:
        """
        獲取事件歷史
        
        Args:
            event_type: 篩選事件類型
            source: 篩選來源
            limit: 返回數量
            
        Returns:
            事件列表
        """
        with self._lock:
            events = self._event_history.copy()
        
        if event_type:
            events = [e for e in events if e.type == event_type]
        
        if source:
            events = [e for e in events if e.source == source]
        
        return events[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """獲取統計信息"""
        with self._lock:
            return {
                "total_events": sum(self._event_count.values()),
                "by_type": {k.value: v for k, v in self._event_count.items()},
                "subscribers": {
                    k.value: len(v) for k, v in self._subscribers.items()
                },
                "history_size": len(self._event_history),
            }
    
    def clear_history(self) -> None:
        """清除歷史"""
        with self._lock:
            self._event_history.clear()
    
    def wait_for_event(
        self,
        event_type: EventType,
        timeout: float = None,
        source: str = None,
    ) -> Optional[Event]:
        """
        等待特定事件（同步調用）
        
        Args:
            event_type: 等待的事件類型
            timeout: 超時時間（秒）
            source: 篩選來源
            
        Returns:
            事件或 None
        """
        import time
        
        result = []
        
        def handler(event: Event):
            result.append(event)
        
        self.subscribe(event_type, handler, "wait_for_event")
        
        start = time.time()
        while not result:
            if timeout and (time.time() - start) > timeout:
                self.unsubscribe(event_type, handler)
                return None
            time.sleep(0.1)
        
        self.unsubscribe(event_type, handler)
        return result[0] if result else None


# ==================== 全域訊息總線 ====================

# 預設的訊息總線實例
_default_bus: Optional[MessageBus] = None


def get_message_bus() -> MessageBus:
    """獲取預設訊息總線"""
    global _default_bus
    if _default_bus is None:
        _default_bus = MessageBus()
    return _default_bus


def set_message_bus(bus: MessageBus) -> None:
    """設置預設訊息總線"""
    global _default_bus
    _default_bus = bus


# ==================== 便捷函數 ====================

def publish_event(
    event_type: EventType,
    source: str,
    data: Dict[str, Any] = None,
    target: str = None,
) -> Event:
    """發布事件（便捷函數）"""
    return get_message_bus().publish_sync(event_type, source, data, target)


def subscribe_event(
    event_type: EventType,
    handler: Callable[[Event], None],
    agent_name: str = None,
) -> None:
    """訂閱事件（便捷函數）"""
    get_message_bus().subscribe(event_type, handler, agent_name)
