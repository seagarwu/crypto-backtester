"""
Unit tests for core.message_bus module
"""

import pytest
import time
from core.message_bus import (
    MessageBus,
    Event,
    EventType,
    get_message_bus,
)


class TestEvent:
    """Test Event dataclass"""
    
    def test_event_creation(self):
        """Test creating an Event"""
        event = Event(
            type=EventType.NEW_MARKET_DATA,
            source="test_agent",
            data={"symbol": "BTCUSDT"},
        )
        
        assert event.type == EventType.NEW_MARKET_DATA
        assert event.source == "test_agent"
        assert event.data["symbol"] == "BTCUSDT"
        assert event.id is not None
        assert event.timestamp is not None
    
    def test_event_with_target(self):
        """Test Event with specific target"""
        event = Event(
            type=EventType.SIGNAL_GENERATED,
            source="strategy",
            target="risk",
            data={"signal": "buy"},
        )
        
        assert event.target == "risk"


class TestMessageBus:
    """Test MessageBus"""
    
    def test_subscribe_and_publish(self):
        """Test basic subscribe and publish"""
        bus = MessageBus()
        received = []
        
        def handler(event):
            received.append(event)
        
        bus.subscribe(EventType.PRICE_ALERT, handler, "test_agent")
        
        event = Event(
            type=EventType.PRICE_ALERT,
            source="market",
            data={"price": 50000},
        )
        bus.publish(event)
        
        assert len(received) == 1
        assert received[0].data["price"] == 50000
    
    def test_unsubscribe(self):
        """Test unsubscribe"""
        bus = MessageBus()
        received = []
        
        def handler(event):
            received.append(event)
        
        bus.subscribe(EventType.PRICE_ALERT, handler, "test")
        
        # Get the wrapped handler that was registered
        handlers = bus._subscribers.get(EventType.PRICE_ALERT, [])
        
        bus.unsubscribe(EventType.PRICE_ALERT, handlers[0])
        
        bus.publish_sync(EventType.PRICE_ALERT, "test", {"value": 1})
        
        assert len(received) == 0
    
    def test_publish_sync(self):
        """Test publish_sync convenience method"""
        bus = MessageBus()
        received = []
        
        def handler(event):
            received.append(event)
        
        bus.subscribe(EventType.SIGNAL_GENERATED, handler, "test")
        
        bus.publish_sync(
            EventType.SIGNAL_GENERATED,
            source="strategy",
            data={"signal": "buy"},
        )
        
        assert len(received) == 1
        assert received[0].data["signal"] == "buy"
    
    def test_multiple_subscribers(self):
        """Test multiple subscribers to same event"""
        bus = MessageBus()
        received1 = []
        received2 = []
        
        def handler1(event):
            received1.append(event)
        
        def handler2(event):
            received2.append(event)
        
        bus.subscribe(EventType.PRICE_ALERT, handler1, "agent1")
        bus.subscribe(EventType.PRICE_ALERT, handler2, "agent2")
        
        bus.publish_sync(EventType.PRICE_ALERT, "source", {"price": 100})
        
        assert len(received1) == 1
        assert len(received2) == 1
    
    def test_event_history(self):
        """Test event history"""
        bus = MessageBus(history_size=10)
        
        for i in range(5):
            bus.publish_sync(EventType.PRICE_ALERT, "source", {"i": i})
        
        history = bus.get_history(limit=10)
        assert len(history) == 5
    
    def test_event_history_limit(self):
        """Test event history size limit"""
        bus = MessageBus(history_size=3)
        
        for i in range(5):
            bus.publish_sync(EventType.PRICE_ALERT, "source", {"i": i})
        
        history = bus.get_history()
        assert len(history) == 3
    
    def test_statistics(self):
        """Test get_statistics"""
        bus = MessageBus()
        
        bus.publish_sync(EventType.PRICE_ALERT, "source", {})
        bus.publish_sync(EventType.PRICE_ALERT, "source", {})
        bus.publish_sync(EventType.SIGNAL_GENERATED, "source", {})
        
        stats = bus.get_statistics()
        
        assert stats["total_events"] == 3
        assert stats["by_type"]["price_alert"] == 2
        assert stats["by_type"]["signal_generated"] == 1
    
    def test_get_history_filter_by_type(self):
        """Test filtering history by event type"""
        bus = MessageBus()
        
        bus.publish_sync(EventType.PRICE_ALERT, "source", {})
        bus.publish_sync(EventType.SIGNAL_GENERATED, "source", {})
        bus.publish_sync(EventType.PRICE_ALERT, "source", {})
        
        price_history = bus.get_history(event_type=EventType.PRICE_ALERT)
        assert len(price_history) == 2
        
        signal_history = bus.get_history(event_type=EventType.SIGNAL_GENERATED)
        assert len(signal_history) == 1


class TestGlobalMessageBus:
    """Test global message bus functions"""
    
    def test_get_default_bus(self):
        """Test get_message_bus returns same instance"""
        bus1 = get_message_bus()
        bus2 = get_message_bus()
        
        assert bus1 is bus2
    
    def test_set_message_bus(self):
        """Test set_message_bus"""
        from core.message_bus import set_message_bus
        
        new_bus = MessageBus()
        set_message_bus(new_bus)
        
        bus = get_message_bus()
        assert bus is new_bus
        
        # Reset to new instance for other tests
        set_message_bus(MessageBus())
