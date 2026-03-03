# -*- coding: utf-8 -*-
"""
量化回測系統主程式

展示如何使用專案模組執行完整的回測流程。
"""

import sys
import os

# 確保可以匯入專案模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data import download_binance_data, DataLoader, datetime_to_timestamp
from strategies import MACrossoverStrategy
from backtest import BacktestEngine
from metrics import calculate_metrics, print_metrics
from reports import export_results


def main():
    """主執行流程"""
    print("=" * 60)
    print("🚀 量化策略回測系統")
    print("=" * 60)

    # =====================
    # 1. 設定參數
    # =====================
    SYMBOL = "BTCUSDT"
    INTERVAL = "1h"
    START_DATE = "2023-01-01"
    END_DATE = "2023-12-31"

    # 策略參數
    SHORT_WINDOW = 20
    LONG_WINDOW = 50

    # 回測參數
    INITIAL_CAPITAL = 10000.0
    COMMISSION_RATE = 0.001  # 0.1%

    print(f"\n📋 設定:")
    print(f"  標的: {SYMBOL}")
    print(f"  時間框架: {INTERVAL}")
    print(f"  期間: {START_DATE} ~ {END_DATE}")
    print(f"  策略: MA Crossover (短:{SHORT_WINDOW}, 長:{LONG_WINDOW})")
    print(f"  初始資金: ${INITIAL_CAPITAL:,.2f}")

    # =====================
    # 2. 下載資料
    # =====================
    print("\n📥 正在下載 Binance 資料...")

    start_ts = datetime_to_timestamp(
        __import__("datetime").datetime.strptime(START_DATE, "%Y-%m-%d")
    )
    end_ts = datetime_to_timestamp(
        __import__("datetime").datetime.strptime(END_DATE, "%Y-%m-%d")
    )

    csv_path = f"data/{SYMBOL}_{INTERVAL}.csv"

    # 嘗試下載（如果失敗，可能是網路問題）
    try:
        download_binance_data(
            symbol=SYMBOL,
            interval=INTERVAL,
            start_time=start_ts,
            end_time=end_ts,
            output_path=csv_path,
        )
    except Exception as e:
        print(f"⚠️ 下載失敗: {e}")
        print("   將使用測試資料繼續...")
        # 使用測試資料
        csv_path = None

    # 如果沒有下載到資料，使用內建測試資料
    if csv_path is None or not os.path.exists(csv_path):
        print("   建立測試資料...")
        csv_path = "data/BTCUSDT_1h.csv"
        _create_test_data(csv_path)

    # =====================
    # 3. 載入資料
    # =====================
    print("\n📂 正在載入資料...")
    loader = DataLoader(csv_path)
    data = loader.load()
    print(f"   載入 {len(data)} 筆資料")
    print(f"   日期範圍: {data['datetime'].min()} ~ {data['datetime'].max()}")

    # =====================
    # 4. 執行策略
    # =====================
    print("\n⚙️ 正在執行策略...")
    strategy = MACrossoverStrategy(
        short_window=SHORT_WINDOW,
        long_window=LONG_WINDOW,
    )
    signals = strategy.on_data(data)
    print(f"   策略執行完成")

    # 統計訊號
    buy_signals = (signals["signal"] == 1).sum()
    sell_signals = (signals["signal"] == -1).sum()
    print(f"   買入訊號: {buy_signals}")
    print(f"   賣出訊號: {sell_signals}")

    # =====================
    # 5. 執行回測
    # =====================
    print("\n🔄 正在執行回測...")
    engine = BacktestEngine(
        initial_capital=INITIAL_CAPITAL,
        commission_rate=COMMISSION_RATE,
    )
    result = engine.run(data, signals)
    print(f"   回測完成")
    print(f"   最終資產: ${result.final_equity:,.2f}")
    print(f"   總交易次數: {result.total_trades}")

    # =====================
    # 6. 計算績效指標
    # =====================
    print("\n📊 正在計算績效指標...")
    metrics = calculate_metrics(result)
    print_metrics(metrics)

    # =====================
    # 7. 輸出報告
    # =====================
    print("📝 正在輸出報告...")
    export_results(
        result=result,
        metrics=metrics,
        output_dir="reports",
        strategy_name=f"MA_Crossover_{SHORT_WINDOW}_{LONG_WINDOW}",
        symbol=SYMBOL,
        interval=INTERVAL,
    )

    print("\n✅ 回測完成！")
    print("=" * 60)


def _create_test_data(output_path: str):
    """建立測試資料"""
    import pandas as pd
    import numpy as np

    # 產生測試用的模擬資料
    np.random.seed(42)
    n = 500

    dates = pd.date_range("2023-01-01", periods=n, freq="h")

    # 隨機漫步產生價格
    returns = np.random.normal(0.0005, 0.02, n)
    close = 30000 * np.exp(np.cumsum(returns))

    # 產生符合 OHLC 邏輯的資料
    data = []
    for i, c in enumerate(close):
        # 產生合理的 OHLC
        volatility = abs(c * np.random.uniform(0.005, 0.02))
        h = c + np.random.uniform(0, volatility)
        l = c - np.random.uniform(0, volatility)
        o = np.random.uniform(l, h)
        v = np.random.uniform(100, 1000)

        data.append({
            "datetime": dates[i],
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": v,
        })

    df = pd.DataFrame(data)

    # 建立目錄
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"   測試資料已儲存至: {output_path}")


if __name__ == "__main__":
    main()
