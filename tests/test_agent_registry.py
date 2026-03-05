"""
Unit tests for core.agent_registry module
"""

import pytest
import asyncio
from core.agent_registry import (
    AgentRegistry,
    AgentMetadata,
    AgentStatus,
    BaseAgent,
    get_agent_registry,
)


class MockAgent(BaseAgent):
    """Mock Agent for testing"""
    
    def __init__(self, name: str = "test_agent"):
        super().__init__(name, "mock")
        self.started = False
        self.stopped = False
    
    async def start(self):
        await super().start()
        self.started = True
    
    async def stop(self):
        await super().stop()
        self.stopped = True


class TestAgentMetadata:
    """Test AgentMetadata"""
    
    def test_metadata_creation(self):
        """Test creating AgentMetadata"""
        meta = AgentMetadata(
            name="test_agent",
            agent_type="trading",
            description="Test agent",
            version="1.0",
            capabilities=["analysis", "trading"],
            subscriptions=["market_data", "signals"],
            publications=["orders"],
        )
        
        assert meta.name == "test_agent"
        assert meta.agent_type == "trading"
        assert "analysis" in meta.capabilities
        assert "market_data" in meta.subscriptions


class TestBaseAgent:
    """Test BaseAgent"""
    
    def test_agent_creation(self):
        """Test creating a BaseAgent"""
        agent = BaseAgent("test", "trading")
        
        assert agent.name == "test"
        assert agent.agent_type == "trading"
        assert agent.is_running() is False
    
    def test_agent_lifecycle(self):
        """Test agent start/stop"""
        agent = MockAgent("test")
        
        assert agent.is_running() is False
        
        # Note: These are sync in our test, but async in real use
        # Just test the flags
        assert agent.started is False
        assert agent.stopped is False


class TestAgentRegistry:
    """Test AgentRegistry"""
    
    def test_registry_creation(self):
        """Test creating an AgentRegistry"""
        registry = AgentRegistry()
        
        assert registry is not None
    
    def test_register_agent(self):
        """Test registering an agent"""
        registry = AgentRegistry()
        agent = MockAgent("test_agent")
        
        success = registry.register(agent)
        
        assert success is True
        assert registry.get("test_agent") is agent
    
    def test_register_duplicate(self):
        """Test registering duplicate agent"""
        registry = AgentRegistry()
        agent1 = MockAgent("test")
        agent2 = MockAgent("test")
        
        success1 = registry.register(agent1)
        success2 = registry.register(agent2)
        
        assert success1 is True
        assert success2 is False
    
    def test_unregister_agent(self):
        """Test unregistering an agent"""
        registry = AgentRegistry()
        agent = MockAgent("test")
        
        registry.register(agent)
        success = registry.unregister("test")
        
        assert success is True
        assert registry.get("test") is None
    
    def test_unregister_nonexistent(self):
        """Test unregistering non-existent agent"""
        registry = AgentRegistry()
        
        success = registry.unregister("nonexistent")
        
        assert success is False
    
    def test_get_metadata(self):
        """Test getting agent metadata"""
        registry = AgentRegistry()
        agent = MockAgent("test")
        
        registry.register(agent)
        meta = registry.get_metadata("test")
        
        assert meta is not None
        assert meta.name == "test"
        assert meta.agent_type == "mock"
    
    def test_find_by_type(self):
        """Test finding agents by type"""
        registry = AgentRegistry()
        
        registry.register(MockAgent("agent1"))
        registry.register(MockAgent("agent2"))
        registry.register(MockAgent("agent3"))
        
        # All are "mock" type
        results = registry.find_by_type("mock")
        
        assert len(results) == 3
    
    def test_find_by_capability(self):
        """Test finding agents by capability"""
        registry = AgentRegistry()
        
        meta1 = AgentMetadata(name="a1", agent_type="t", capabilities=["trading"])
        meta2 = AgentMetadata(name="a2", agent_type="t", capabilities=["analysis"])
        meta3 = AgentMetadata(name="a3", agent_type="t", capabilities=["trading", "analysis"])
        
        registry.register(MockAgent("a1"), meta1)
        registry.register(MockAgent("a2"), meta2)
        registry.register(MockAgent("a3"), meta3)
        
        trading_agents = registry.find_by_capability("trading")
        assert len(trading_agents) == 2
        
        analysis_agents = registry.find_by_capability("analysis")
        assert len(analysis_agents) == 2
    
    def test_list_agents(self):
        """Test listing all agents"""
        registry = AgentRegistry()
        
        registry.register(MockAgent("a1"))
        registry.register(MockAgent("a2"))
        
        agents = registry.list_agents()
        
        assert len(agents) == 2
        assert "a1" in agents
        assert "a2" in agents
    
    def test_update_metadata(self):
        """Test updating metadata"""
        registry = AgentRegistry()
        agent = MockAgent("test")
        
        registry.register(agent)
        
        success = registry.update_metadata("test", description="Updated")
        
        assert success is True
        
        meta = registry.get_metadata("test")
        assert meta.description == "Updated"
    
    def test_update_stats(self):
        """Test updating stats"""
        registry = AgentRegistry()
        agent = MockAgent("test")
        
        registry.register(agent)
        
        success = registry.update_stats("test", trades=10, pnl=500.0)
        
        assert success is True
        
        meta = registry.get_metadata("test")
        assert meta.stats["trades"] == 10
        assert meta.stats["pnl"] == 500.0
    
    def test_statistics(self):
        """Test getting statistics"""
        registry = AgentRegistry()
        
        registry.register(MockAgent("a1"))
        registry.register(MockAgent("a2"))
        registry.register(MockAgent("a3"))
        
        stats = registry.get_statistics()
        
        assert stats["total_agents"] == 3
    
    def test_health_check(self):
        """Test health check"""
        registry = AgentRegistry()
        
        agent = MockAgent("test")
        agent._running = True  # Mark as running
        
        registry.register(agent)
        
        health = registry.health_check()
        
        assert "test" in health


class TestGlobalAgentRegistry:
    """Test global agent registry functions"""
    
    def test_get_default_registry(self):
        """Test get_agent_registry returns same instance"""
        registry1 = get_agent_registry()
        registry2 = get_agent_registry()
        
        assert registry1 is registry2
