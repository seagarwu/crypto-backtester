# BTCUSDT_軌道策略

## 策略摘要

雙週期布林通道逆勢策略。
使用 4H 布林通道判斷是否進入可做多或可做空的準備狀態，再用 1H 布林通道與成交量確認進場，目標是做短線均值回歸。

## 策略規格
- 名稱: BTCUSDT_BBand_Reversion
- 描述: 4H 與 1H 雙週期布林通道逆勢策略，搭配成交量過濾與固定 3% 止損。
- 指標: ['BBand', 'Volume']
- 進場規則: 當 4H 觸碰下軌時準備做多，1H 觸碰下軌且成交量大於過去 20 根均量 2 倍時做多；當 4H 觸碰上軌時準備做空，1H 觸碰上軌且成交量大於過去 20 根均量 2 倍時做空。
- 出場規則: 做多時碰到 1H 上軌出場，做空時碰到 1H 下軌出場，另有固定 3% 止損。
- 參數: {'bb_period': 20, 'bb_std': 2.0, 'volume_ma_period': 20, 'volume_multiplier': 2.0, 'stop_loss_pct': 0.03, 'higher_timeframe': '4h', 'entry_timeframe': '1h'}
- 時間框架: 1h
## 設計決策

- 大週期使用 4H。
- 進出場使用 1H。
- 觸碰即視為條件成立，不等待收盤確認。
- 布林通道參數使用預設 20 / 2。
- 成交量條件為當前量大於過去 20 根平均量的 2 倍。
- 做多與做空邏輯完全鏡像。

## 生成檔案

- /media/nexcom/data/alan/crypto-backtester/strategies/generated/BTCUSDT_BBand_Reversion.py

- 2026-03-13 22:20: 用戶: "好..."
- 2026-03-13 22:20: 助手: "[EXECUTE] 正在為您執行 BTCUSDT_BBand_Reversion 策略：結合 4H 與 1H 布林通道逆勢邏輯，搭配 2 倍成交量過濾與 3% 固定止損。..."
- 2026-03-13 22:32: 用戶: "好..."
- 2026-03-13 22:32: 助手: "[EXECUTE] 正在為您執行 BTCUSDT_BBand_Reversion 策略：結合 4H 與 1H 雙週期布林通道逆勢邏輯，搭配成交量過濾與 3% 固定止損。..."
- 2026-03-13 22:43: 用戶: "好..."
- 2026-03-13 22:43: 助手: "[EXECUTE] 我將開始執行 BTCUSDT_BBand_Reversion 策略。該策略結合了 4H 與 1H 布林通道逆勢邏輯，並使用成交量爆發作為過濾條件，同時設置 3% 固定止損。..."
- 2026-03-14 01:21: 用戶: "好..."
- 2026-03-14 01:21: 助手: "[EXECUTE] 我將為您執行 BTCUSDT_BBand_Reversion 策略：結合 4H 與 1H 雙週期布林通道，搭配 2 倍成交量過濾進行逆勢交易，並設置 3% 固定止損。..."
- 2026-03-14 01:30: 用戶: "好..."
- 2026-03-14 01:30: 助手: "[EXECUTE] 好的，我將開始為您執行 BTCUSDT_BBand_Reversion 策略。該策略結合 4H 與 1H 雙週期布林通道，搭配成交量倍數過濾，並設有 3% 固定止損。..."
- 2026-03-14 01:33: 用戶: "好..."
- 2026-03-14 01:33: 助手: "[EXECUTE] 準備執行 BTCUSDT 雙週期布林通道逆勢策略（4H/1H），包含成交量倍增過濾與固定 3% 止損。..."
- /media/nexcom/data/alan/crypto-backtester/strategies/generated/BTCUSDT_BBand_Reversion.py