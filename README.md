# crypto-backtester

一個**可擴充的加密貨幣量化策略回測骨架**，專為打造「專屬量化研究與回測 agent」的第一階段基礎。

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

## 🎯 專案目標

本專案旨在建立一個穩定、清楚、可擴充的量化回測系統，支持：

- ✅ 多策略回測
- ✅ 策略參數掃描
- ✅ Walk-forward testing
- ✅ 報表輸出
- ✅ 與 Agent / Workflow 系統整合
- ✅ 未來可接 LangGraph / Multi-agent 架構

## 📁 專案結構

```
crypto-backtester/
├── data/                    # 資料相關模組
├── strategies/             # 策略模組
├── backtest/              # 回測引擎
├── metrics/               # 績效指標
├── reports/               # 報告輸出
├── tests/                 # 測試
├── configs/               # 配置
├── scripts/               # 腳本
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
from data import download_binance_data, datetime_to_timestamp
from datetime import datetime

start = datetime_to_timestamp(datetime(2023, 1, 1))
end = datetime_to_timestamp(datetime(2023, 12, 31))

download_binance_data(
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

data = load_csv("data/BTCUSDT_1h.csv")
strategy = MACrossoverStrategy(short_window=20, long_window=50)
signals = strategy.on_data(data)
result = run_backtest(data=data, signals=signals, initial_capital=10000.0)
metrics = calculate_metrics(result)
print_metrics(metrics)
export_results(result=result, metrics=metrics, output_dir="reports")
```

或使用腳本：

```bash
python scripts/run_backtest.py
```

## 📖 功能說明

- **data/**: Binance API 下載 + CSV 載入驗證
- **strategies/**: 策略基底類別 + 均線交叉策略
- **backtest/**: 回測引擎核心
- **metrics/**: 完整績效指標計算
- **reports/**: CSV + Markdown 報告輸出

## 🧪 測試

```bash
pytest tests/ -v
```

## 🔮 未來擴充方向

- 參數網格掃描
- 更多策略（RSI, MACD, Bollinger Bands）
- Walk-forward testing
- Pair Trading / Statistical Arbitrage
- LangGraph / Multi-agent 整合

## 📄 License

MIT License
