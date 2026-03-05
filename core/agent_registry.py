"""
Agent Registry - Agent 註冊與發現系統

功能：
- 動態註冊/註銷 Agents
- Agent 發現
- Agent 狀態管理
- Agent 健康檢查
"""

from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading
import uuid


class AgentStatus(Enum):
    """Agent 狀態"""
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    UNHEALTHY = "unhealthy"


@dataclass
class AgentMetadata:
    """Agent 元數據"""
    name: str
    agent_type: str
    description: str = ""
    version: str = "1.0"
    
    # 能力標籤
    capabilities: List[str] = field(default_factory=list)
    
    # 訂閱的事件類型
    subscriptions: List[str] = field(default_factory=list)
    
    # 發布的事件類型
    publications: List[str] = field(default_factory=list)
    
    # 配置
    config: Dict[str, Any] = field(default_factory=dict)
    
    # 統計
    stats: Dict[str, Any] = field(default_factory=dict)
    
    # 最後活動時間
    last_active: datetime = field(default_factory=datetime.now)


class BaseAgent:
    """Agent 基底類別"""
    
    def __init__(self, name: str, agent_type: str):
        self.name = name
        self.agent_type = agent_type
        self._running = False
    
    async def start(self):
        """啟動 Agent"""
        self._running = True
    
    async def stop(self):
        """停止 Agent"""
        self._running = False
    
    def is_running(self) -> bool:
        """是否運行中"""
        return self._running
    
    def get_metadata(self) -> AgentMetadata:
        """獲取元數據"""
        return AgentMetadata(
            name=self.name,
            agent_type=self.agent_type,
        )


class AgentRegistry:
    """
    Agent 註冊表
    
    功能：
    - 註冊/註銷 Agent
    - 查找 Agent
    - 狀態管理
    - 健康檢查
    """
    
    def __init__(self):
        """初始化註冊表"""
        self._agents: Dict[str, BaseAgent] = {}
        self._metadata: Dict[str, AgentMetadata] = {}
        self._lock = threading.RLock()
        
        # 健康檢查
        self._health_check_interval = 60  # 秒
        self._health_check_callback: Optional[Callable] = None
    
    def register(
        self,
        agent: BaseAgent,
        metadata: AgentMetadata = None,
    ) -> bool:
        """
        註冊 Agent
        
        Args:
            agent: Agent 實例
            metadata: 元數據（可選）
            
        Returns:
            是否成功
        """
        with self._lock:
            if agent.name in self._agents:
                print(f"⚠️ Agent 已存在: {agent.name}")
                return False
            
            self._agents[agent.name] = agent
            
            # 如果沒有提供 metadata，創建默認的
            if metadata is None:
                metadata = AgentMetadata(
                    name=agent.name,
                    agent_type=agent.agent_type,
                )
            
            self._metadata[agent.name] = metadata
            
            print(f"✅ Agent 註冊: {agent.name} ({agent.agent_type})")
            
            return True
    
    def unregister(self, name: str) -> bool:
        """
        註銷 Agent
        
        Args:
            name: Agent 名稱
            
        Returns:
            是否成功
        """
        with self._lock:
            if name not in self._agents:
                return False
            
            # 停止 Agent
            try:
                # 如果有 stop 方法，調用它
                if hasattr(self._agents[name], 'stop'):
                    self._agents[name].stop()
            except Exception as e:
                print(f"⚠️ 停止 Agent 失敗: {e}")
            
            del self._agents[name]
            del self._metadata[name]
            
            print(f"🗑️ Agent 已註銷: {name}")
            
            return True
    
    def get(self, name: str) -> Optional[BaseAgent]:
        """獲取 Agent"""
        with self._lock:
            return self._agents.get(name)
    
    def get_metadata(self, name: str) -> Optional[AgentMetadata]:
        """獲取 Agent 元數據"""
        with self._lock:
            return self._metadata.get(name)
    
    def find_by_type(self, agent_type: str) -> List[BaseAgent]:
        """根據類型查找 Agents"""
        with self._lock:
            return [
                agent for name, agent in self._agents.items()
                if self._metadata.get(name, AgentMetadata("", "")).agent_type == agent_type
            ]
    
    def find_by_capability(self, capability: str) -> List[BaseAgent]:
        """根據能力查找 Agents"""
        with self._lock:
            result = []
            for name, meta in self._metadata.items():
                if capability in meta.capabilities:
                    result.append(self._agents[name])
            return result
    
    def find_by_subscription(self, event_type: str) -> List[BaseAgent]:
        """根據訂閱的事件類型查找 Agents"""
        with self._lock:
            result = []
            for name, meta in self._metadata.items():
                if event_type in meta.subscriptions:
                    result.append(self._agents[name])
            return result
    
    def list_agents(self) -> List[str]:
        """列出所有 Agent"""
        with self._lock:
            return list(self._agents.keys())
    
    def list_by_status(self, status: AgentStatus) -> List[str]:
        """根據狀態列出 Agents"""
        # 這裡需要從 metadata 或 agent 獲取狀態
        # 暫時返回所有
        return self.list_agents()
    
    def update_metadata(self, name: str, **kwargs) -> bool:
        """更新 Agent 元數據"""
        with self._lock:
            if name not in self._metadata:
                return False
            
            meta = self._metadata[name]
            for key, value in kwargs.items():
                if hasattr(meta, key):
                    setattr(meta, key, value)
            
            meta.last_active = datetime.now()
            
            return True
    
    def update_stats(self, name: str, **stats) -> bool:
        """更新 Agent 統計"""
        with self._lock:
            if name not in self._metadata:
                return False
            
            self._metadata[name].stats.update(stats)
            self._metadata[name].last_active = datetime.now()
            
            return True
    
    def get_all_metadata(self) -> List[AgentMetadata]:
        """獲取所有 Agent 元數據"""
        with self._lock:
            return list(self._metadata.values())
    
    def get_statistics(self) -> Dict[str, Any]:
        """獲取統計信息"""
        with self._lock:
            by_type = {}
            for meta in self._metadata.values():
                if meta.agent_type not in by_type:
                    by_type[meta.agent_type] = 0
                by_type[meta.agent_type] += 1
            
            return {
                "total_agents": len(self._agents),
                "by_type": by_type,
                "agents": [name for name in self._agents.keys()],
            }
    
    def health_check(self) -> Dict[str, Any]:
        """健康檢查"""
        results = {}
        
        with self._lock:
            for name, agent in self._agents.items():
                meta = self._metadata.get(name)
                
                # 檢查運行狀態
                is_healthy = True
                issues = []
                
                if not agent.is_running():
                    is_healthy = False
                    issues.append("Agent not running")
                
                # 檢查最後活動時間
                if meta:
                    inactive_seconds = (datetime.now() - meta.last_active).total_seconds()
                    if inactive_seconds > self._health_check_interval * 2:
                        is_healthy = False
                        issues.append(f"Inactive for {inactive_seconds}s")
                
                results[name] = {
                    "healthy": is_healthy,
                    "issues": issues,
                }
        
        return results


# ==================== 便捷函數 ====================

_default_registry: Optional[AgentRegistry] = None


def get_agent_registry() -> AgentRegistry:
    """獲取默認 Agent 註冊表"""
    global _default_registry
    if _default_registry is None:
        _default_registry = AgentRegistry()
    return _default_registry


def register_agent(agent: BaseAgent, metadata: AgentMetadata = None) -> bool:
    """便捷註冊 Agent"""
    return get_agent_registry().register(agent, metadata)


def unregister_agent(name: str) -> bool:
    """便捷註銷 Agent"""
    return get_agent_registry().unregister(name)


def find_agent(name: str) -> Optional[BaseAgent]:
    """便捷查找 Agent"""
    return get_agent_registry().get(name)


def find_agents_by_type(agent_type: str) -> List[BaseAgent]:
    """便捷按類型查找"""
    return get_agent_registry().find_by_type(agent_type)
