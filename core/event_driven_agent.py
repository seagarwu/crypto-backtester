"""
Event-Driven Agent - 事件驅動 Agent 基底類別

所有 Agent 應該繼承此類別，以支援事件驅動架構。
"""

from typing import Dict, List, Any, Optional, Callable
from abc import ABC, abstractmethod
import threading
import asyncio

from core.message_bus import MessageBus, Event, EventType, get_message_bus
from core.agent_registry import BaseAgent, AgentMetadata, AgentStatus


class EventDrivenAgent(BaseAgent):
    """
    事件驅動 Agent 基底類別
    
    特性：
    - 透過 Message Bus 通訊
    - 訂閱感興趣的事件
    - 發布事件通知其他 Agents
    - 支援啟動/停止/暫停
    """
    
    def __init__(
        self,
        name: str,
        agent_type: str,
        message_bus: MessageBus = None,
        auto_register: bool = True,
    ):
        """
        初始化 Event-Driven Agent
        
        Args:
            name: Agent 名稱
            agent_type: Agent 類型
            message_bus: 訊息總線（可選）
            auto_register: 是否自動註冊
        """
        super().__init__(name, agent_type)
        
        # 訊息總線
        self.message_bus = message_bus or get_message_bus()
        
        # 訂閱的事件
        self._subscriptions: Dict[EventType, Callable] = {}
        
        # 狀態
        self._paused = False
        
        # 執行緒安全
        self._lock = threading.RLock()
        
        # 統計
        self.events_received = 0
        self.events_published = 0
        
        # 自動註冊
        if auto_register:
            self._register_with_bus()
    
    def _register_with_bus(self):
        """向訊息總線註冊"""
        pass  # 子類在 subscribe 後會自動處理
    
    def subscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], None],
    ):
        """
        訂閱事件
        
        Args:
            event_type: 事件類型
            handler: 處理函數
        """
        with self._lock:
            self._subscriptions[event_type] = handler
        
        # 向訊息總線註冊
        self.message_bus.subscribe(event_type, handler, self.name)
        
        print(f"📬 [{self.name}] 訂閱: {event_type.value}")
    
    def unsubscribe(self, event_type: EventType):
        """取消訂閱"""
        with self._lock:
            handler = self._subscriptions.pop(event_type, None)
        
        if handler:
            self.message_bus.unsubscribe(event_type, handler)
    
    def publish(
        self,
        event_type: EventType,
        data: Dict[str, Any] = None,
        target: str = None,
    ):
        """
        發布事件
        
        Args:
            event_type: 事件類型
            data: 事件數據
            target: 目標 Agent（可選）
        """
        event = Event(
            type=event_type,
            source=self.name,
            target=target,
            data=data or {},
        )
        
        self.message_bus.publish(event)
        
        with self._lock:
            self.events_published += 1
    
    async def start(self):
        """啟動 Agent"""
        await super().start()
        self._paused = False
        print(f"🚀 [{self.name}] 已啟動")
    
    async def stop(self):
        """停止 Agent"""
        await super().stop()
        
        # 取消所有訂閱
        with self._lock:
            for event_type in list(self._subscriptions.keys()):
                self.unsubscribe(event_type)
        
        print(f"🛑 [{self.name}] 已停止")
    
    def pause(self):
        """暫停 Agent"""
        self._paused = True
        print(f"⏸️ [{self.name}] 已暫停")
    
    def resume(self):
        """恢復 Agent"""
        self._paused = False
        print(f"▶️ [{self.name}] 已恢復")
    
    def is_paused(self) -> bool:
        """是否暫停"""
        return self._paused
    
    def get_metadata(self) -> AgentMetadata:
        """獲取元數據"""
        return AgentMetadata(
            name=self.name,
            agent_type=self.agent_type,
            subscriptions=[e.value for e in self._subscriptions.keys()],
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """獲取統計"""
        return {
            "name": self.name,
            "type": self.agent_type,
            "running": self._running,
            "paused": self._paused,
            "subscriptions": len(self._subscriptions),
            "events_received": self.events_received,
            "events_published": self.events_published,
        }


class AsyncEventDrivenAgent(EventDrivenAgent):
    """異步版本的 Event-Driven Agent"""
    
    def __init__(self, name: str, agent_type: str, message_bus: MessageBus = None):
        super().__init__(name, agent_type, message_bus)
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._processing = False
    
    async def start(self):
        """啟動 Agent"""
        await super().start()
        self._processing = True
        # 啟動事件處理循環
        asyncio.create_task(self._process_events())
    
    async def stop(self):
        """停止 Agent"""
        self._processing = False
        await super().stop()
    
    async def _process_events(self):
        """異步處理事件"""
        while self._processing:
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=1.0
                )
                
                if not self._paused:
                    await self.handle_event(event)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"❌ [{self.name}] 處理事件錯誤: {e}")
    
    async def handle_event(self, event: Event):
        """處理事件（子類實現）"""
        pass
    
    def publish(
        self,
        event_type: EventType,
        data: Dict[str, Any] = None,
        target: str = None,
    ):
        """發布事件（異步版本）"""
        event = Event(
            type=event_type,
            source=self.name,
            target=target,
            data=data or {},
        )
        self.message_bus.publish(event)
        
        with self._lock:
            self.events_published += 1
