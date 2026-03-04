# Crypto Backtester - Project Architecture

```mermaid
flowchart TB
    subgraph Data["📂 Data Module"]
        direction TB
        Binance[binance.py<br/>Binance API Download]
        Loader[loader.py<br/>CSV Loader]
    end

    subgraph Strategies["📊 Strategies Module"]
        direction TB
        Base[strategies/base.py<br/>BaseStrategy]
        MA[strategies/ma_crossover.py<br/>MACrossoverStrategy]
    end

    subgraph Backtest["⚡ Backtest Engine"]
        direction TB
        Engine[backtest/engine.py<br/>BacktestEngine]
    end

    subgraph Metrics["📈 Metrics Module"]
        direction TB
        Perf[metrics/performance.py<br/>Performance Metrics]
    end

    subgraph Reports["📄 Reports Module"]
        direction TB
        Output[reports/output.py<br/>CSV/MD Export]
    end

    subgraph Experiments["🔬 Experiments Module"]
        direction TB
        Grid[experiments/grid_search.py<br/>Grid Search]
        Walk[experiments/walk_forward.py<br/>Walk-Forward]
    end

    subgraph VSS["👁️ VSS Module - Market Analysis"]
        direction TB
        VSS_Types[vss/types.py<br/>Type Definitions]
        VSS_Analyzer[vss/analyzer.py<br/>Market Analyzer]
        VSS_Observer[vss/observer.py<br/>Real-time Observer]
    end

    subgraph Alignment["🎯 Alignment Module - Human-AI"]
        direction TB
        Align_Types[alignment/types.py<br/>Decision Types]
        Align_Eval[alignment/evaluator.py<br/>Alignment Evaluator]
        Align_Rec[alignment/recorder.py<br/>Decision Recorder]
        Align_Ctrl[alignment/controller.py<br/>Decision Controller]
    end

    subgraph Agents["🤖 Multi-Agent Trading System"]
        direction TB
        MarketMonitor[agents/market_monitor_agent.py<br/>Market Monitor]
        Strategy[agents/strategy_agent.py<br/>Strategy Agent]
        Risk[agents/risk_agent.py<br/>Risk Agent]
        Trading[agents/trading_agent.py<br/>Trading Agent]
        System[agents/trading_system.py<br/>Trading System]
    end

    subgraph Configs["⚙️ Configuration"]
        direction TB
        Config[configs/backtest_config.py<br/>Config]
    end

    %% Data Flow
    Binance --> Loader
    Loader --> Strategies
    Strategies --> Backtest
    Backtest --> Metrics
    Metrics --> Reports
    Metrics --> Experiments
    Experiments --> Backtest

    %% Integration with Advanced Modules
    Data --> VSS_Observer
    VSS_Observer --> VSS_Analyzer
    VSS_Analyzer --> Align_Ctrl
    
    Align_Ctrl --> Align_Eval
    Align_Eval --> Align_Rec
    Align_Rec --> Align_Types
    
    VSS_Analyzer --> Agent_Workflow
    Agent_Workflow --> Agent_Example

    %% Trading System Flow
    Binance --> MarketMonitor
    MarketMonitor --> Strategy
    Strategy --> Risk
    Risk --> Trading
    Trading --> System

    %% Styling
    classDef module fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef core fill:#fff3e0,stroke:#e65100,stroke-width:3px
    classDef advanced fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef agents fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    
    class Data,Strategies,Backtest,Metrics,Reports,Experiments,Configs module
    class Binance,Loader,Engine,Perf,Output,Grid,Walk core
    class VSS,Alignment,Agents advanced
    class MarketMonitor,Strategy,Risk,Trading,System agents
```

## Multi-Agent Trading Flow

```mermaid
sequenceDiagram
    participant User
    participant System as Trading System
    participant Market as Market Monitor
    participant Strategy as Strategy Agent
    participant Risk as Risk Agent
    participant Trading as Trading Agent
    
    User->>System: start()
    System->>Market: start() 啟動定時抓取
    Market->>Market: 每小時抓取最新資料
    
    loop 每個週期
        System->>Market: get_latest_data()
        Market-->>System: 回傳 DataFrame
        
        System->>Strategy: get_signal()
        Strategy-->>System: signal + metrics
        
        System->>Risk: evaluate_trade()
        Risk-->>System: risk decision
        
        alt 風險允許交易
            System->>Trading: execute_trade()
            Trading-->>System: trade result
        else 風險過高
            System->>System: skip trade
        end
        
        System->>User: 回傳結果
    end
```

## Agent Responsibilities

| Agent | 職責 | 輸入 | 輸出 |
|-------|------|------|------|
| **Market Monitor** | 定時抓取資料 | Binance API | CSV/DB |
| **Strategy** | 產生訊號 | 歷史資料 | buy/sell/hold |
| **Risk** | 風險評估 | 訊號+市場資料 | 執行決定 |
| **Trading** | 執行交易 | 風險決定 | 訂單結果 |
| **System** | 協調所有 Agent | - | 完整流程 |

## Module Dependencies

```mermaid
flowchart LR
    subgraph Input["Inputs"]
        Binance
    end
    
    subgraph Core["Core Pipeline"]
        Loader --> Strategies --> Backtest --> Metrics --> Reports
    end
    
    subgraph Research["Research"]
        Metrics --> Grid
        Grid --> Walk
        Walk -.->|optimize| Strategies
    end
    
    subgraph Advanced["Advanced Features"]
        VSS_Observer --> VSS_Analyzer
        VSS_Analyzer --> Alignment
        Alignment --> Agents
    end
    
    Input --> Core
    Core --> Research
    Core --> Advanced
```

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
