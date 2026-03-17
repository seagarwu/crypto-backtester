# crypto-backtester

一個**可擴充的加密貨幣量化策略回測骨架**，專為打造「專屬量化研究與回測 agent」的第一階段基礎。

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

## 🎯 專案目標

本專案旨在建立一個穩定、清楚、可擴充的量化回測系統，支持：

- ✅ 多策略回測
- ✅ 策略參數掃描 (Grid Search)
- ✅ Optuna 貝葉斯優化
- ✅ Walk-forward testing
- ✅ 報告系統 (視覺化 + HTML)
- ✅ 與 Agent / Workflow 系統整合
- ✅ 未來可接 LangGraph / Multi-agent 架構

## 📁 專案結構

```text
crypto-backtester/
├── data/                    # 資料相關模組
│   ├── binance.py          # Binance API 下載（含分頁功能）
│   └── loader.py           # CSV 資料載入
├── strategies/             # 策略模組
│   ├── base.py            # 策略基底類別
│   └── ma_crossover.py    # 均線交叉策略
├── backtest/              # 回測引擎
│   └── engine.py          # 回測核心（含 execution_price 參數）
├── metrics/               # 績效指標
│   └── performance.py     # 績效計算
├── reports/               # 報告輸出
│   ├── output.py          # 結果匯出
│   └── generator.py      # 視覺化報告生成
├── experiments/           # 研究實驗模組
│   ├── grid_search.py     # 參數網格掃描
│   ├── walk_forward.py    # Walk-forward 測試
│   └── optuna_search.py   # Optuna 貝葉斯優化
├── vss/                   # VSS 市場分析模組
│   ├── types.py           # 類型定義
│   ├── analyzer.py       # 市場分析器
│   └── observer.py       # 市場觀察器
├── alignment/             # 人機對齊模組
│   ├── types.py           # 決策類型
│   ├── evaluator.py      # 對齊評估器
│   ├── recorder.py       # 判斷記錄器
│   └── controller.py     # 決策控制器
├── tests/                 # 測試
├── scripts/               # 腳本
├── configs/               # 配置
├── requirements.txt
├── pyproject.toml
├── VSS_TRADING_ARCHITECTURE.md  # VSS 架構說明
└── README.md
```

## 🚀 快速開始

### 1. 安裝依賴

```bash
pip install -r requirements.txt
```

建議使用 Python 3.10 建立乾淨虛擬環境。完整測試已驗證的依賴組合為：

- `numpy==1.26.4`
- `pandas==2.0.3`
- `optuna==4.8.0`

若你在本機執行測試時遇到 `numpy.dtype size changed`，通常代表 `numpy/pandas` binary mismatch，請重建虛擬環境或重新安裝上述版本組合。

### 2. 下載 Binance 歷史資料

```python
from data import download_klines_range, datetime_to_timestamp
from datetime import datetime

# 下載大量資料（自動分頁）
start = datetime_to_timestamp(datetime(2023, 1, 1))
end = datetime_to_timestamp(datetime(2024, 1, 1))

df = download_klines_range(
    symbol="BTCUSDT",
    interval="1h",
    start_time=start,
    end_time=end,
    output_path="data/BTCUSDT_1h.csv",
)
```

### 3. 執行回測

```python
from data import load_csv
from strategies import MACrossoverStrategy
from backtest import run_backtest
from metrics import calculate_metrics, print_metrics
from reports import export_results

# 1. 載入資料
data = load_csv("data/BTCUSDT_1h.csv")

# 2. 執行策略
strategy = MACrossoverStrategy(short_window=20, long_window=50)
signals = strategy.on_data(data)

# 3. 執行回測（可選 next_open 避免 lookahead）
result = run_backtest(
    data=data,
    signals=signals,
    initial_capital=10000.0,
    execution_price="next_open",  # 新功能：避免 lookahead
)

# 4. 計算績效指標
metrics = calculate_metrics(result)
print_metrics(metrics)

# 5. 匯出報告
export_results(
    result=result,
    metrics=metrics,
    output_dir="reports",
    strategy_name="MA_Crossover",
    symbol="BTCUSDT",
    interval="1h",
)
```

## 🤖 Multi-Agent Loop Bootstrap

這個 repo 現在提供最小可用的 human-in-the-loop 協作基礎設施：

- `research/strategy_spec.md`: strategy-agent 的規格與 human decision checkpoint
- `research/implementation_note.md`: engineer-agent 的實作記錄
- `research/backtest_report.md` 與 `research/backtest_report.json`: backtest-agent 的標準化輸出
- `research/iteration_log.md`: 每輪 loop 的審計軌跡
- `research/strategy_handoff.json`: strategy -> engineer 的機器可讀交接
- `research/engineer_handoff.json`: engineer -> backtest 的機器可讀交接
- `research/backtest_handoff.json`: backtest -> evaluator 的機器可讀交接
- `research/evaluation_handoff.json`: evaluator -> strategy 的機器可讀交接
- `research_contracts.py`: 共用契約與標準化輸出邏輯
- `schemas/backtest_report.schema.json`: 機器可驗證的 report schema
- `schemas/*_handoff.schema.json`: agent 間 handoff 的 JSON schema

初始化 workspace：

```bash
python scripts/init_agent_workspace.py
```

初始化 autonomous 任務工作區：

```bash
python scripts/init_autonomous_task.py \
    strategy-loop \
    "Run the human-in-the-loop strategy workflow across multiple sessions" \
    --goal "Keep research artifacts updated after each iteration"
```

初始化 deep-research 工作區：

```bash
python scripts/init_deep_research.py \
    "btc-mean-reversion" \
    "Compare candidate mean-reversion strategy families for BTCUSDT 1h" \
    --dimension "market regime" \
    --dimension "indicator family" \
    --dimension "risk controls"
```

執行標準化 backtest-agent 流程：

```bash
python scripts/run_agent_backtest.py \
    --data data/BTCUSDT_1h.csv \
    --strategy ma_crossover \
    --iteration 1 \
    --short-window 20 \
    --long-window 50 \
    --execution-price next_open
```

這個流程會：

- 使用 repo 內既有回測引擎與報表輸出
- 更新 `research/backtest_report.md`
- 更新 `research/backtest_report.json`
- 追加 `research/iteration_log.md`
- 保留人類決策為是否繼續下一輪的唯一最終判定

建議編排方式：

- `.research/<run>/`: 用於 deep-research 前置調研與候選策略比較
- `research/`: 用於 canonical strategy loop artifacts
- `.autonomous/<task>/`: 用於長任務 session 追蹤、handoff 與恢復執行

如果你想把這套 agent 治理方式搬到其他 repo，可參考：

- [docs/AGENT_GOVERNANCE_TEMPLATE.md](docs/AGENT_GOVERNANCE_TEMPLATE.md)

## 🔬 參數網格掃描 (Grid Search)

### 使用腳本

```bash
python scripts/run_grid_search.py \
    --data data/BTCUSDT_1h.csv \
    --short 10,20,30 \
    --long 50,100,200 \
    --score sharpe_ratio \
    --top-k 10 \
    --out reports/
```

### 使用 API

```python
from data import load_csv
from strategies import MACrossoverStrategy
from experiments import run_grid_search, select_top_k

data = load_csv("data/BTCUSDT_1h.csv")

# 參數網格
param_ranges = {
    "short_window": [10, 20, 30],
    "long_window": [50, 100, 200],
}

# 執行網格掃描
results = run_grid_search(
    data=data,
    strategy_class=MACrossoverStrategy,
    param_ranges=param_ranges,
    scoring="sharpe_ratio",
)

# 取得 Top 10
top_10 = select_top_k(results, k=10, by="sharpe_ratio")
```

## 🔄 Walk-Forward Testing

### 使用腳本

```bash
python scripts/run_walk_forward.py \
    --data data/BTCUSDT_1h.csv \
    --train-bars 2000 \
    --test-bars 500 \
    --step-bars 500 \
    --short 10,20,30 \
    --long 50,100 \
    --out reports/
```

### 使用 API

```python
from data import load_csv
from strategies import MACrossoverStrategy
from experiments import run_walk_forward

data = load_csv("data/BTCUSDT_1h.csv")

result = run_walk_forward(
    data=data,
    strategy_class=MACrossoverStrategy,
    param_ranges={"short_window": [10, 20], "long_window": [50, 100]},
    train_bars=2000,
    test_bars=500,
    scoring="sharpe_ratio",
)

# 取得結果
folds_df = result["folds_results"]
stitched_equity = result["stitched_equity"]
summary = result["summary"]
```

## 📖 功能說明

### 資料模組 (data/)

| 模組 | 功能 |
|------|------|
| `binance.py` | 從 Binance API 下載歷史 K 線資料（含自動分頁） |
| `loader.py` | 載入 CSV 並驗證資料品質 |
| `parse_interval_to_ms()` | 將 interval 轉換為毫秒數 |

### 策略模組 (strategies/)

| 策略 | 說明 |
|------|------|
| `BaseStrategy` | 策略基底類別，定義訊號產生介面 |
| `MACrossoverStrategy` | 移動平均線交叉策略 |

### 回測引擎 (backtest/)

- 支援初始資金設定
- 支援交易成本（commission）
- 支援 `execution_price` 參數：`"close"` 或 `"next_open"`
- 輸出資產曲線與交易記錄

### 績效指標 (metrics/)

- 總報酬率、年化報酬率、最大回撤
- Sharpe Ratio、Sortino Ratio、Calmar Ratio
- 勝率、盈利因子、平均盈虧比

### 實驗模組 (experiments/)

- `grid_search.py`: 參數網格掃描
- `walk_forward.py`: Walk-forward 測試
- `optuna_search.py`: Optuna 貝葉斯優化

## 🧠 Optuna 貝葉斯優化

使用 TPE (Tree-structured Parzen Estimator) 演算法進行高效的參數優化。

### 使用腳本

```bash
python scripts/run_optuna.py \
    --data data/BTCUSDT_1h.csv \
    --trials 100 \
    --short-low 5 \
    --short-high 50 \
    --long-low 20 \
    --long-high 200 \
    --objective sharpe_ratio
```

### 使用 API

```python
from data import load_csv
from strategies import MACrossoverStrategy
from experiments import run_optuna_optimization

data = load_csv("data/BTCUSDT_1h.csv")

# 參數空間
param_space = {
    "short_window": {"low": 5, "high": 50, "type": "int"},
    "long_window": {"low": 20, "high": 200, "type": "int"},
}

# 執行 Optuna 優化
result = run_optuna_optimization(
    data=data,
    strategy_class=MACrossoverStrategy,
    param_space=param_space,
    objective="sharpe_ratio",
    n_trials=100,
)

# 取得最佳參數
best_params = result["best_params"]
best_value = result["best_value"]
```

### 帶約束的優化

```python
# 約束：short_window < long_window
def constraints(params):
    return params["short_window"] < params["long_window"]

result = run_optuna_optimization(
    data=data,
    strategy_class=MACrossoverStrategy,
    param_space=param_space,
    objective="sharpe_ratio",
    n_trials=50,
    constraints=constraints,
)
```

## 📊 報告系統

### 使用 API

```python
from reports import ReportGenerator, generate_optimization_report
import pandas as pd

# 建立報告生成器
gen = ReportGenerator(output_dir="reports")

# 繪製資金曲線
gen.plot_equity_curve(equity_df, title="My Equity Curve")

# 繪製回撤曲線
gen.plot_drawdown(equity_df, title="My Drawdown")

# 繪製參數優化熱力圖
gen.plot_optimization_heatmap(
    results_df,
    param_x="short_window",
    param_y="long_window",
    metric="sharpe_ratio",
)

# 自動生成完整報告
generate_optimization_report(
    results_df=optimization_results,
    output_dir="reports",
    title="My Optimization Report",
)
```

## VSS 市場分析模組 (vss/)

市場狀態視覺化（VSS）分析，實現即時市場監控與人類對齊。

| 模組 | 功能 |
|------|------|
| `types.py` | 類型定義 (`MarketState`, `HumanJudgment`, `VSSAnalysisResult`, `AlignmentResult`) |
| `analyzer.py` | `VSSAnalyzer` - 市場分析器，分析 K 線形態、趨勢、動量 |
| `observer.py` | `VSSObserver` - 市場觀察器，回測中即時觸發分析 |

### 人機對齊模組 (alignment/)

人類判斷與 VSS 分析結果的對齊評估與決策控制。

| 模組 | 功能 |
|------|------|
| `types.py` | 決策類型 (`Decision`, `DecisionReason`) |
| `evaluator.py` | `AlignmentEvaluator` - 對齊評估器，計算人類與 VSS 判斷的一致性 |
| `recorder.py` | `JudgmentRecorder` - 判斷記錄器，持久化人類判斷與對齊結果 |
| `controller.py` | `DecisionController` - 決策控制器，根據對齊分數決定是否執行交易 |

## 🧪 測試

```bash
python -m pytest tests/ -v
```

## 📝 設計取捨說明

1. **不回測最優化**：第一階段專注在骨架建立，暫不實作複雜的參數優化
2. **撮合邏輯簡化**：使用收盤價或下一根開盤價模擬交易
3. **僅支援 Long 方向**：均線策略只實作做多，未來可擴充做空

## 🔮 未來擴充方向

- 更多策略（RSI, MACD, Bollinger Bands）
- Pair Trading / Statistical Arbitrage
- LangGraph / Multi-agent 整合

## 📄 License

MIT License
