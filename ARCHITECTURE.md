# Crypto Backtester - Project Architecture

## 系統架構總覽

```mermaid
flowchart TB
    subgraph Core["🎯 Core - 事件驅動核心"]
        direction TB
        MB[message_bus.py<br/>Message Bus]
        WF[workflow.py<br/>Workflow Engine]
        AQ[approval_queue.py<br/>Human Approval]
        AR[agent_registry.py<br/>Agent Registry]
        EDA[event_driven_agent.py<br/>Event-Driven Agent]
    end

    subgraph Data["📂 Data Module"]
        Binance[binance.py<br/>Binance API]
        Loader[loader.py<br/>CSV Loader]
    end

    subgraph Strategies["📊 Strategies"]
        MA[ma_crossover.py<br/>MA Crossover]
    end

    subgraph Agents["🤖 Multi-Agent System"]
        Market[agents/market_monitor_agent.py<br/>Market Monitor]
        Strategy[agents/strategy_agent.py<br/>Strategy]
        Risk[agents/risk_agent.py<br/>Risk]
        Trading[agents/trading_agent.py<br/>Trading]
    end

    subgraph VSS["👁️ VSS Module"]
        VSS_An[vss/analyzer.py]
        VSS_Ob[vss/observer.py]
    end

    subgraph Alignment["🎯 Alignment"]
        Eval[alignment/evaluator.py]
        Rec[alignment/recorder.py]
    end

    %% 核心連接
    MB --> WF
    MB --> AQ
    MB --> AR
    EDA --> MB
    
    %% Agent 連接
    Binance --> Market
    Market --> MB
    MB --> Strategy
    MB --> Risk
    Strategy --> MB
    Risk --> MB
    Risk --> AQ
    AQ --> MB
    MB --> Trading
```

## Event-Driven Flow

```mermaid
sequenceDiagram
    participant Bus as Message Bus
    participant Market as Market Monitor
    participant Strategy as Strategy Agent
    participant Risk as Risk Agent
    participant Human as Human
    participant Trading as Trading Agent
    
    Market->>Bus: 發布: new_market_data
    Bus->>Strategy: 傳遞: new_market_data
    
    Strategy->>Bus: 發布: signal_generated
    Bus->>Risk: 傳遞: signal
    
    Risk->>Bus: 發布: risk_assessment
    Bus->>Human: 需要審批?
    
    alt 需要審批
        Human->>Bus: 批准/拒絕
    end
    
    Bus->>Trading: 執行交易
    Trading->>Bus: 發布: trade_executed
```

## Human-in-the-Loop

```mermaid
flowchart LR
    subgraph Rules["審批規則"]
        R1[金額 > $10,000]
        R2[連續虧損 > 5次]
        R3[日交易 > 20次]
        R4[總虧損 > $5,000]
    end
    
    subgraph Queue["Approval Queue"]
        Req[審批請求]
        Wait[等待人類]
        Decision[批准/拒絕]
    end
    
    R1 --> Req
    Req --> Wait
    Wait --> Decision
    
    Decision -->|通過| Trading[執行交易]
    Decision -->|拒絕| Skip[跳過交易]
```

## 動態 Workflow 配置

```yaml
# workflow.yaml
name: trading_workflow
entry_point: market_monitor

nodes:
  - name: market_monitor
    agent_type: market_monitor
    actions:
      - type: publish
        event: new_market_data
    
  - name: strategy
    agent_type: strategy
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
```

## 功能對照表

| 模組 | 功能 | 實現 |
|------|------|------|
| Message Bus | 事件發布/訂閱 | `core/message_bus.py` |
| Workflow | 動態流程配置 | `core/workflow.py` |
| Approval Queue | 人類審批 | `core/approval_queue.py` |
| Agent Registry | Agent 註冊發現 | `core/agent_registry.py` |
| Event-Driven Agent | Agent 基底類別 | `core/event_driven_agent.py` |

## Agent Workflow

```mermaid
flowchart LR
    Market[📊 Market<br/>Monitor Agent] -->|signals| Risk[⚠️ Risk<br/>Management Agent]
    Risk -->|decisions| Strategy[📈 Strategy<br/>Dev Agent]
    Strategy -->|results| Backtest[⚡ Backtest<br/>Agent]
    Backtest -->|reports| Human[👤 Human<br/>Manager]
    
    Human -->|feedback| Alignment[🎯 Alignment<br/>Module]
    Alignment -->|learning| Risk
```

## Data Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Data
    participant Strategy
    participant Backtest
    participant Metrics
    participant Reports
    
    User->>CLI: Run backtest
    CLI->>Data: Load CSV
    Data-->>CLI: DataFrame
    CLI->>Strategy: Generate signals
    Strategy-->>CLI: Signals
    CLI->>Backtest: Run backtest
    Backtest-->>CLI: Result
    CLI->>Metrics: Calculate metrics
    Metrics-->>CLI: Metrics dict
    CLI->>Reports: Export reports
    Reports-->>User: CSV/MD files
```
