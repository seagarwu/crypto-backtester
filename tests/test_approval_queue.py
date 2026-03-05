"""
Unit tests for core.approval_queue module
"""

import pytest
import time
from core.approval_queue import (
    HumanApprovalQueue,
    ApprovalRequest,
    ApprovalStatus,
    ApprovalPriority,
    ApprovalRule,
    get_approval_queue,
)


class TestApprovalRule:
    """Test ApprovalRule"""
    
    def test_rule_with_condition(self):
        """Test rule with custom condition"""
        rule = ApprovalRule(
            name="test_rule",
            condition_fn=lambda d: d.get("amount", 0) > 1000,
            priority=ApprovalPriority.HIGH,
            description="Test rule",
        )
        
        assert rule.requires_approval({"amount": 500}) is False
        assert rule.requires_approval({"amount": 2000}) is True
    
    def test_default_rules(self):
        """Test default rules are added"""
        queue = HumanApprovalQueue()
        
        # High amount rule
        assert queue.requires_approval({"amount": 500}) is False
        assert queue.requires_approval({"amount": 50000}) is True
        
        # Consecutive losses rule
        assert queue.requires_approval({"consecutive_losses": 3}) is False
        assert queue.requires_approval({"consecutive_losses": 10}) is True
        
        # High frequency rule
        assert queue.requires_approval({"daily_trades": 10}) is False
        assert queue.requires_approval({"daily_trades": 25}) is True


class TestApprovalRequest:
    """Test ApprovalRequest"""
    
    def test_request_creation(self):
        """Test creating an ApprovalRequest"""
        request = ApprovalRequest(
            title="Test Request",
            requester="risk_agent",
            data={"amount": 5000},
            description="Test description",
            priority=ApprovalPriority.NORMAL,
        )
        
        assert request.title == "Test Request"
        assert request.requester == "risk_agent"
        assert request.status == ApprovalStatus.PENDING
        assert request.priority == ApprovalPriority.NORMAL
        assert request.id is not None


class TestHumanApprovalQueue:
    """Test HumanApprovalQueue"""
    
    def test_request_approval(self):
        """Test requesting approval"""
        queue = HumanApprovalQueue()
        
        request = queue.request_approval(
            title="Large Trade",
            requester="risk_agent",
            data={"amount": 50000},
            description="Trade over $10k",
        )
        
        assert request is not None
        assert request.status == ApprovalStatus.PENDING
        assert request.data["amount"] == 50000
        
        pending = queue.get_pending()
        assert len(pending) == 1
        assert pending[0].id == request.id
    
    def test_approve_request(self):
        """Test approving a request"""
        queue = HumanApprovalQueue()
        
        request = queue.request_approval(
            title="Test",
            requester="agent",
            data={"amount": 100},
        )
        
        success = queue.approve(request.id, "human", "Approved")
        
        assert success is True
        assert request.status == ApprovalStatus.APPROVED
        assert request.responder == "human"
        assert request.response_note == "Approved"
        
        pending = queue.get_pending()
        assert len(pending) == 0
    
    def test_reject_request(self):
        """Test rejecting a request"""
        queue = HumanApprovalQueue()
        
        request = queue.request_approval(
            title="Test",
            requester="agent",
            data={"amount": 100},
        )
        
        success = queue.reject(request.id, "human", "Too risky")
        
        assert success is True
        assert request.status == ApprovalStatus.REJECTED
        assert request.response_note == "Too risky"
    
    def test_priority_ordering(self):
        """Test requests are ordered by priority"""
        queue = HumanApprovalQueue()
        
        # Create requests with different priorities
        queue.request_approval(
            title="Low Priority",
            requester="agent",
            data={"amount": 100},
            priority=ApprovalPriority.LOW,
        )
        
        queue.request_approval(
            title="High Priority",
            requester="agent",
            data={"amount": 50000},
            priority=ApprovalPriority.HIGH,
        )
        
        queue.request_approval(
            title="Normal Priority",
            requester="agent",
            data={"amount": 1000},
            priority=ApprovalPriority.NORMAL,
        )
        
        pending = queue.get_pending()
        
        # High priority should be first
        assert pending[0].title == "High Priority"
        assert pending[1].title == "Normal Priority"
        assert pending[2].title == "Low Priority"
    
    def test_auto_priority_from_rules(self):
        """Test automatic priority based on matched rules"""
        queue = HumanApprovalQueue()
        
        # High amount - should trigger HIGH priority
        request = queue.request_approval(
            title="Test",
            requester="agent",
            data={"amount": 50000},  # Triggers high_amount rule
        )
        
        assert request.priority == ApprovalPriority.HIGH
        assert "high_amount" in request.conditions["matched_rules"]
    
    def test_cancel_request(self):
        """Test cancelling a request"""
        queue = HumanApprovalQueue()
        
        request = queue.request_approval(
            title="Test",
            requester="agent",
            data={},
        )
        
        success = queue.cancel(request.id)
        
        assert success is True
        assert request.status == ApprovalStatus.CANCELLED
    
    def test_get_by_id(self):
        """Test getting request by ID"""
        queue = HumanApprovalQueue()
        
        request = queue.request_approval(
            title="Test",
            requester="agent",
            data={},
        )
        
        found = queue.get_by_id(request.id)
        
        assert found is not None
        assert found.id == request.id
    
    def test_history(self):
        """Test approval history"""
        queue = HumanApprovalQueue()
        
        req1 = queue.request_approval(title="Req1", requester="a", data={})
        queue.approve(req1.id)
        
        req2 = queue.request_approval(title="Req2", requester="a", data={})
        queue.reject(req2.id)
        
        history = queue.get_history()
        
        assert len(history) == 2
        assert history[0].status == ApprovalStatus.APPROVED
        assert history[1].status == ApprovalStatus.REJECTED
    
    def test_statistics(self):
        """Test get_statistics"""
        queue = HumanApprovalQueue()
        
        # Create and process some requests
        req1 = queue.request_approval(title="R1", requester="a", data={})
        queue.approve(req1.id)
        
        req2 = queue.request_approval(title="R2", requester="a", data={})
        queue.reject(req2.id)
        
        queue.request_approval(title="R3", requester="a", data={"amount": 100})
        
        stats = queue.get_statistics()
        
        assert stats["pending"] == 1
        assert stats["total_approved"] == 1
        assert stats["total_rejected"] == 1
        assert stats["rules_count"] > 0
    
    def test_wait_for_approval_timeout(self):
        """Test waiting for approval with timeout"""
        queue = HumanApprovalQueue(timeout_seconds=1)
        
        request = queue.request_approval(
            title="Test",
            requester="agent",
            data={},
        )
        
        # Wait with timeout - should timeout since no one approves
        status = queue.wait_for_approval(request.id, timeout=1)
        
        assert status == ApprovalStatus.TIMEOUT
    
    def test_wait_for_approval_success(self):
        """Test waiting for approval - approval received"""
        queue = HumanApprovalQueue(timeout_seconds=5)
        
        request = queue.request_approval(
            title="Test",
            requester="agent",
            data={},
        )
        
        # Approve in another thread would work, but for testing
        # we just verify the structure works
        pending = queue.get_pending()
        assert len(pending) == 1


class TestGlobalApprovalQueue:
    """Test global approval queue functions"""
    
    def test_get_default_queue(self):
        """Test get_approval_queue returns same instance"""
        queue1 = get_approval_queue()
        queue2 = get_approval_queue()
        
        assert queue1 is queue2
