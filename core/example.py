"""
Core 模組使用範例

展示如何使用事件驅動架構。
"""

from core import (
    MessageBus,
    Event,
    EventType,
    HumanApprovalQueue,
    ApprovalStatus,
)


def example_message_bus():
    """訊息總線範例"""
    print("\n" + "="*50)
    print("範例 1: Message Bus")
    print("="*50)
    
    bus = MessageBus()
    
    # 訂閱者
    def on_price_alert(event: Event):
        print(f"   收到價格警報: {event.data}")
    
    bus.subscribe(EventType.PRICE_ALERT, on_price_alert, "alert_agent")
    
    # 發布事件
    bus.publish_sync(
        event_type=EventType.PRICE_ALERT,
        source="market_monitor",
        data={"symbol": "BTCUSDT", "price": 50000},
    )
    
    # 查看統計
    stats = bus.get_statistics()
    print(f"\n統計: {stats}")


def example_approval_queue():
    """審批隊列範例"""
    print("\n" + "="*50)
    print("範例 2: Human Approval Queue")
    print("="*50)
    
    queue = HumanApprovalQueue()
    
    # 測試需要審批的情況
    print("\n1. 小金額（不需要審批）:")
    result = queue.requires_approval({"amount": 1000})
    print(f"   amount=1000 需要審批: {result}")
    
    print("\n2. 大金額（需要審批）:")
    result = queue.requires_approval({"amount": 50000})
    print(f"   amount=50000 需要審批: {result}")
    
    # 請求審批
    print("\n3. 請求審批:")
    request = queue.request_approval(
        title="大額交易",
        requester="risk_agent",
        data={"amount": 50000, "symbol": "BTCUSDT"},
        description="嘗試購買 50000 USDT 的 BTC",
    )
    print(f"   請求 ID: {request.id}")
    print(f"   狀態: {request.status.value}")
    
    # 批准
    print("\n4. 批准請求:")
    success = queue.approve(request.id, "human", "批准此交易")
    print(f"   成功: {success}")


def main():
    """執行範例"""
    print("="*50)
    print("Core 模組使用範例")
    print("="*50)
    
    example_message_bus()
    example_approval_queue()
    
    print("\n" + "="*50)
    print("完成!")
    print("="*50)


if __name__ == "__main__":
    main()
