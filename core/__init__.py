"""
Core - 核心模組

提供事件驅動架構的基礎設施：
- Message Bus (訊息總線)
- Workflow (工作流配置)
- Approval Queue (人類審批)
- Agent Registry (Agent 註冊)
- LLM Manager (模型管理)
"""

from .message_bus import (
    MessageBus,
    Event,
    EventType,
    get_message_bus,
    set_message_bus,
    publish_event,
    subscribe_event,
)

from .workflow import (
    WorkflowEngine,
    Workflow,
    Node,
    Condition,
    Action,
    ConditionType,
    ActionType,
    create_workflow_engine,
    load_workflow,
    DEFAULT_WORKFLOW,
)

from .approval_queue import (
    HumanApprovalQueue,
    ApprovalRequest,
    ApprovalStatus,
    ApprovalPriority,
    ApprovalRule,
    get_approval_queue,
    set_approval_queue,
    request_approval,
    approve,
    reject,
)

from .agent_registry import (
    AgentRegistry,
    AgentMetadata,
    AgentStatus,
    BaseAgent,
    get_agent_registry,
    register_agent,
    unregister_agent,
    find_agent,
    find_agents_by_type,
)

from .event_driven_agent import (
    EventDrivenAgent,
    AsyncEventDrivenAgent,
)

from .llm_manager import (
    LLMManager,
    ModelConfig,
    ModelProvider,
    AVAILABLE_MODELS,
    TASK_MODEL_MAPPING,
    get_llm_manager,
    set_llm_manager,
    get_llm,
    get_llm_for_task,
    list_available_models,
    recommend_model,
)


__all__ = [
    # Message Bus
    "MessageBus",
    "Event",
    "EventType",
    "get_message_bus",
    "set_message_bus",
    "publish_event",
    "subscribe_event",
    # Workflow
    "WorkflowEngine",
    "Workflow",
    "Node",
    "Condition",
    "Action",
    "ConditionType",
    "ActionType",
    "create_workflow_engine",
    "load_workflow",
    "DEFAULT_WORKFLOW",
    # Approval Queue
    "HumanApprovalQueue",
    "ApprovalRequest",
    "ApprovalStatus",
    "ApprovalPriority",
    "ApprovalRule",
    "get_approval_queue",
    "set_approval_queue",
    "request_approval",
    "approve",
    "reject",
    # Agent Registry
    "AgentRegistry",
    "AgentMetadata",
    "AgentStatus",
    "BaseAgent",
    "get_agent_registry",
    "register_agent",
    "unregister_agent",
    "find_agent",
    "find_agents_by_type",
    # Event-Driven Agent
    "EventDrivenAgent",
    "AsyncEventDrivenAgent",
    # LLM Manager
    "LLMManager",
    "ModelConfig",
    "ModelProvider",
    "AVAILABLE_MODELS",
    "TASK_MODEL_MAPPING",
    "get_llm_manager",
    "set_llm_manager",
    "get_llm",
    "get_llm_for_task",
    "list_available_models",
    "recommend_model",
]
