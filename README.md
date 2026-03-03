# crypto-backtester

一個**可擴充的加密貨幣量化策略回測骨架**，專為打造「專屬量化研究與回測 agent」的第一階段基礎。

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

## 🎯 專案目標

本專案旨在建立一個穩定、清楚、可擴充的量化回測系統，支持：

- ✅ 多策略回測
- ✅ 策略參數掃描 (Grid Search)
- ✅ Walk-forward testing
- ✅ 報表輸出
- ✅ 與 Agent / Workflow 系統整合
- ✅ 未來可接 LangGraph / Multi-agent 架構

## 📁 專案結構

```
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
│   └── output.py          # 結果匯出
├── experiments/           # 研究實驗模組
│   ├── grid_search.py     # 參數網格掃描
│   └── walk_forward.py    # Walk-forward 測試
├── tests/                 # 測試
├── scripts/               # 腳本
│   ├── run_backtest.py
│   ├── run_grid_search.py
│   └── run_walk_forward.py
├── configs/               # 配置
│   └── backtest_config.py
├── requirements.txt
├── pyproject.toml
└── README.md
```

## 🚀 快速開始

### 1. 安裝依賴

```bash
pip install -r requirements.txt
```

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

## 🧪 測試

```bash
pytest tests/ -v
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
