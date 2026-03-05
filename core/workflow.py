"""
Workflow - 動態工作流配置系統

支援：
- YAML/JSON 配置
- 動態 Agent 註冊
- 條件分支
- Human-in-the-loop
"""

from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import yaml
import json
from pathlib import Path


class ConditionType(Enum):
    """條件類型"""
    ALWAYS = "always"
    EQUALS = "equals"
    GREATER_THAN = "gt"
    LESS_THAN = "lt"
    IN_LIST = "in"
    REGEX = "regex"


class ActionType(Enum):
    """動作類型"""
    PUBLISH = "publish"
    ROUTE = "route"
    APPROVAL = "approval"  # Human-in-the-loop
    LOG = "log"
    TRANSFORM = "transform"


@dataclass
class Condition:
    """條件"""
    type: ConditionType = ConditionType.ALWAYS
    field: str = ""  # 要檢查的欄位
    value: Any = None
    
    def evaluate(self, data: Dict[str, Any]) -> bool:
        """評估條件"""
        if self.type == ConditionType.ALWAYS:
            return True
        
        field_value = data.get(self.field)
        
        if self.type == ConditionType.EQUALS:
            return field_value == self.value
        
        if self.type == ConditionType.GREATER_THAN:
            return (field_value or 0) > self.value
        
        if self.type == ConditionType.LESS_THAN:
            return (field_value or 0) < self.value
        
        if self.type == ConditionType.IN_LIST:
            return field_value in (self.value or [])
        
        return True


@dataclass
class Action:
    """動作"""
    type: ActionType
    event: str = ""  # 發布的事件類型
    target: Optional[str] = None  # 目標 Agent
    data: Dict[str, Any] = field(default_factory=dict)
    transform: Optional[Callable] = None  # 數據轉換函數


@dataclass
class Node:
    """流程節點"""
    name: str
    agent_type: str  # Agent 類型
    conditions: List[Condition] = field(default_factory=list)
    actions: List[Action] = field(default_factory=list)
    on_approval_required: Optional[str] = None  # 需要審批時的處理
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Workflow:
    """工作流"""
    name: str
    version: str = "1.0"
    description: str = ""
    nodes: List[Node] = field(default_factory=list)
    entry_point: str = ""  # 起始節點
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkflowEngine:
    """
    工作流引擎
    
    負責：
    - 加載配置
    - 執行流程
    - 條件判斷
    - 人類審批觸發
    """
    
    def __init__(self, message_bus=None):
        """
        初始化工作流引擎
        
        Args:
            message_bus: 訊息總線實例
        """
        self.message_bus = message_bus
        self.workflows: Dict[str, Workflow] = {}
        self._agents: Dict[str, Any] = {}  # 註冊的 Agents
    
    def load_from_yaml(self, path: str) -> Workflow:
        """從 YAML 文件加載工作流"""
        with open(path, 'r') as f:
            config = yaml.safe_load(f)
        return self._parse_config(config)
    
    def load_from_json(self, path: str) -> Workflow:
        """從 JSON 文件加載工作流"""
        with open(path, 'r') as f:
            config = json.load(f)
        return self._parse_config(config)
    
    def load_from_dict(self, config: Dict) -> Workflow:
        """從字典加載工作流"""
        return self._parse_config(config)
    
    def _parse_config(self, config: Dict) -> Workflow:
        """解析配置"""
        # 解析節點
        nodes = []
        for node_config in config.get("nodes", []):
            # 解析條件
            conditions = []
            for cond in node_config.get("conditions", []):
                conditions.append(Condition(
                    type=ConditionType(cond.get("type", "always")),
                    field=cond.get("field", ""),
                    value=cond.get("value"),
                ))
            
            # 解析動作
            actions = []
            for act in node_config.get("actions", []):
                actions.append(Action(
                    type=ActionType(act.get("type", "publish")),
                    event=act.get("event", ""),
                    target=act.get("target"),
                    data=act.get("data", {}),
                ))
            
            nodes.append(Node(
                name=node_config["name"],
                agent_type=node_config.get("agent_type", ""),
                conditions=conditions,
                actions=actions,
                on_approval_required=node_config.get("on_approval_required"),
                metadata=node_config.get("metadata", {}),
            ))
        
        workflow = Workflow(
            name=config.get("name", "unnamed"),
            version=config.get("version", "1.0"),
            description=config.get("description", ""),
            nodes=nodes,
            entry_point=config.get("entry_point", ""),
            metadata=config.get("metadata", {}),
        )
        
        self.workflows[workflow.name] = workflow
        return workflow
    
    def register_agent(self, name: str, agent: Any) -> None:
        """註冊 Agent"""
        self._agents[name] = agent
        print(f"✅ Agent 註冊: {name}")
    
    def get_agent(self, name: str) -> Optional[Any]:
        """獲取 Agent"""
        return self._agents.get(name)
    
    def execute(self, workflow_name: str, initial_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        執行工作流
        
        Args:
            workflow_name: 工作流名稱
            initial_data: 初始數據
            
        Returns:
            執行結果
        """
        workflow = self.workflows.get(workflow_name)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_name}")
        
        # 從 entry point 開始
        current_node = None
        for node in workflow.nodes:
            if node.name == workflow.entry_point:
                current_node = node
                break
        
        if not current_node:
            raise ValueError(f"Entry point not found: {workflow.entry_point}")
        
        # 執行流程
        results = {"status": "running", "steps": []}
        data = initial_data.copy()
        
        while current_node:
            step_result = self._execute_node(current_node, data)
            results["steps"].append(step_result)
            
            # 決定下一步
            if step_result.get("status") == "approval_required":
                results["status"] = "waiting_approval"
                break
            
            if step_result.get("status") == "error":
                results["status"] = "error"
                break
            
            # 更新數據
            data.update(step_result.get("data", {}))
            
            # 找下一個節點
            next_node_name = step_result.get("next_node")
            if not next_node_name:
                break
            
            current_node = None
            for node in workflow.nodes:
                if node.name == next_node_name:
                    current_node = node
                    break
        
        results["final_data"] = data
        return results
    
    def _execute_node(self, node: Node, data: Dict[str, Any]) -> Dict[str, Any]:
        """執行單個節點"""
        # 檢查條件
        for condition in node.conditions:
            if not condition.evaluate(data):
                return {
                    "node": node.name,
                    "status": "skipped",
                    "reason": f"Condition not met: {condition.type.value}",
                    "data": {},
                }
        
        # 獲取 Agent
        agent = self._agents.get(node.agent_type)
        
        # 執行動作
        results = {"node": node.name, "actions": []}
        
        for action in node.actions:
            action_result = self._execute_action(action, agent, data)
            results["actions"].append(action_result)
            
            # 如果需要人類審批
            if action_result.get("requires_approval"):
                return {
                    "node": node.name,
                    "status": "approval_required",
                    "approval_data": action_result,
                    "data": data,
                }
        
        return {
            "node": node.name,
            "status": "completed",
            "data": results,
        }
    
    def _execute_action(
        self,
        action: Action,
        agent: Any,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """執行動作"""
        if action.type == ActionType.PUBLISH:
            # 發布事件
            if self.message_bus:
                from core.message_bus import EventType
                event_type = EventType(action.event)
                self.message_bus.publish_sync(event_type, action.target or "workflow", action.data)
            
            return {"type": "publish", "event": action.event}
        
        elif action.type == ActionType.APPROVAL:
            # 檢查是否需要人類審批
            # 這裡應該調用 Approval Queue
            requires_approval = self._check_approval_required(action, data)
            
            return {
                "type": "approval",
                "requires_approval": requires_approval,
                "data": data,
            }
        
        return {"type": action.type.value, "status": "done"}
    
    def _check_approval_required(self, action: Action, data: Dict[str, Any]) -> bool:
        """檢查是否需要人類審批"""
        # 實現審批邏輯
        # 例如：金額 > 10000, 虧損 > 5000 等
        
        # 這裡先簡單實現，實際需要連接 Approval Queue
        amount = data.get("amount", 0)
        threshold = action.data.get("threshold", 10000)
        
        return amount > threshold
    
    def list_workflows(self) -> List[str]:
        """列出所有工作流"""
        return list(self.workflows.keys())
    
    def get_workflow(self, name: str) -> Optional[Workflow]:
        """獲取工作流"""
        return self.workflows.get(name)


# ==================== 預設配置示例 ====================

DEFAULT_WORKFLOW = """
name: trading_workflow
version: 1.0
description: 標準交易流程

entry_point: market_monitor

nodes:
  - name: market_monitor
    agent_type: market_monitor
    conditions: []
    actions:
      - type: publish
        event: new_market_data
    
  - name: strategy
    agent_type: strategy
    conditions: []
    actions:
      - type: publish
        event: signal_generated
    
  - name: risk_check
    agent_type: risk
    conditions:
      - type: gt
        field: amount
        value: 10000
    actions:
      - type: approval
        threshold: 10000
        event: human_approval_request
    on_approval_required: wait_for_approval
    
  - name: execution
    agent_type: trading
    conditions: []
    actions:
      - type: publish
        event: trade_executed
"""

# ==================== 便捷函數 ====================

def create_workflow_engine(message_bus=None) -> WorkflowEngine:
    """創建工作流引擎"""
    return WorkflowEngine(message_bus)


def load_workflow(path: str, message_bus=None) -> Workflow:
    """便捷加載工作流"""
    engine = create_workflow_engine(message_bus)
    
    if path.endswith('.yaml') or path.endswith('.yml'):
        return engine.load_from_yaml(path)
    elif path.endswith('.json'):
        return engine.load_from_json(path)
    else:
        raise ValueError("Unsupported file format. Use .yaml or .json")
