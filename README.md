# 📊 Quant Backtest - 量化策略回測骨架

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

一個**可擴充的量化策略回測骨架**，專為打造「專屬量化研究與回測 agent」的第一階段基礎。

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
quant-backtest/
├── data/                    # 資料相關模組
│   ├── __init__.py
│   ├── binance.py          # Binance API 下載
│   └── loader.py           # CSV 資料載入
├── strategies/             # 策略模組
│   ├── __init__.py
│   ├── base.py            # 策略基底類別
│   └── ma_crossover.py    # 均線交叉策略
├── backtest/              # 回測引擎
│   ├── __init__.py
│   └── engine.py          # 回測核心
├── metrics/               # 績效指標
│   ├── __init__.py
│   └── performance.py     # 績效計算
├── reports/               # 報告輸出
│   ├── __init__.py
│   └── output.py          # 結果匯出
├── tests/                 # 測試
│   ├── __init__.py
│   ├── test_binance.py
│   ├── test_loader.py
│   ├── test_strategy.py
│   └── test_backtest.py
├── configs/               # 配置
│   └── backtest_config.py
├── scripts/               # 腳本
│   └── run_backtest.py
├── data/                  # 資料目錄
├── reports/               # 報告目錄
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

# 方式一：直接下載並存 CSV
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

# 1. 載入資料
data = load_csv("data/BTCUSDT_1h.csv")

# 2. 執行策略
strategy = MACrossoverStrategy(short_window=20, long_window=50)
signals = strategy.on_data(data)

# 3. 執行回測
result = run_backtest(
    data=data,
    signals=signals,
    initial_capital=10000.0,
    commission_rate=0.001,
)

# 4. 計算績效指標
metrics = calculate_metrics(result)
print_metrics(metrics)

# 5. 匯出報告
export_results(
    result=result,
    metrics=metrics,
    output_dir="reports",
    strategy_name="MA_Crossover_20_50",
    symbol="BTCUSDT",
    interval="1h",
)
```

或使用腳本：

```bash
python scripts/run_backtest.py
```

## 📖 功能說明

### 資料模組 (data/)

| 模組 | 功能 |
|------|------|
| `binance.py` | 從 Binance API 下載歷史 K 線資料 |
| `loader.py` | 載入 CSV 並驗證資料品質 |

### 策略模組 (strategies/)

| 策略 | 說明 |
|------|------|
| `BaseStrategy` | 策略基底類別，定義訊號產生介面 |
| `MACrossoverStrategy` | 移動平均線交叉策略 |

### 回測引擎 (backtest/)

- 支援初始資金設定
- 支援交易成本（commission）
- 支援固定比例或全倉交易
- 輸出資產曲線與交易記錄

### 績效指標 (metrics/)

- 總報酬率
- 年化報酬率
- 最大回撤 (Max Drawdown)
- Sharpe Ratio
- Sortino Ratio
- Calmar Ratio
- 勝率、盈利因子、平均盈虧比

### 報告輸出 (reports/)

- 交易記錄 CSV
- 資產曲線 CSV
- Markdown 格式回測報告

## 🧪 測試

```bash
pytest tests/ -v
```

## 📝 設計取捨說明

1. **不回測最優化**：第一階段專注在骨架建立，暫不實作複雜的參數優化
2. **撮合邏輯簡化**：使用收盤價模擬交易，未來可擴充為逐筆撮合
3. **僅支援 Long 方向**：均線策略只實作做多，未來可擴充做空
4. ** periods_per_year 預設**：績效指標使用預設值，視資料頻率調整

## 🔮 未來擴充方向

### 短期 (Phase 2)
- [ ] 更多策略（RSI, MACD, Bollinger Bands）
- [ ] 參數網格掃描 (Grid Search)
- [ ] 簡單的圖表輸出

### 中期 (Phase 3)
- [ ] Walk-forward testing
- [ ] 多元資料來源（Yahoo Finance, 期貨）
- [ ] Pair Trading 策略框架

### 長期 (Phase 4+)
- [ ] Statistical Arbitrage
- [ ] Factor Research 框架
- [ ] News/Event-driven Signals
- [ ] LangGraph / Multi-agent 整合

## 📄 License

MIT License

## 👤 作者

Quant Researcher
