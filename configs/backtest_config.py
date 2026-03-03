# -*- coding: utf-8 -*-
"""
回測配置

定義預設的回測參數。
"""

# 回測參數
BACKTEST_CONFIG = {
    "initial_capital": 10000.0,      # 初始資金
    "commission_rate": 0.001,         # 手續費率 (0.1%)
    "position_size": 1.0,              # 倉位比例 (1.0 = 全倉)
    "slippage": 0.0,                  # 滑點（尚未實作）
}

# 策略參數
STRATEGY_CONFIG = {
    "ma_crossover": {
        "short_window": 20,
        "long_window": 50,
    },
}

# 資料來源
DATA_CONFIG = {
    "binance": {
        "default_symbol": "BTCUSDT",
        "default_interval": "1h",
    },
}

# 輸出設定
REPORT_CONFIG = {
    "output_dir": "reports",
    "save_trades": True,
    "save_equity": True,
    "save_report": True,
}

# 績效指標計算
METRICS_CONFIG = {
    "risk_free_rate": 0.0,
    "periods_per_year": {
        "1m": 365 * 24 * 60,
        "5m": 365 * 24 * 12,
        "15m": 365 * 24 * 4,
        "1h": 365 * 24,
        "4h": 365 * 6,
        "1d": 365,
    },
}
