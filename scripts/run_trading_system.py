#!/usr/bin/env python3
"""
Multi-Agent Trading System 啟動腳本

使用方式:
    python run_trading_system.py              # 預設 (paper 模式)
    python run_trading_system.py --live       # 實盤模式
    python run_trading_system.py --once       # 執行一次
    python run_trading_system.py --help       # 查看幫助
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# 確保可以匯入模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser(
        description="Multi-Agent Trading System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  python run_trading_system.py                  預設 paper 模式
  python run_trading_system.py --live          實盤交易
  python run_trading_system.py --once          只執行一次
  python run_trading_system.py --symbols BTCUSDT ETHUSDT
  python run_trading_system.py --interval 1h,4h,1d
  python run_trading_system.py --backtest --start 2024-01-01 --end 2024-12-31
  python run_trading_system.py --download --years 10
        """
    )
    
    # ===== 交易模式 =====
    parser.add_argument(
        "--mode", 
        choices=["paper", "live"], 
        default="paper",
        help="交易模式 (default: paper)"
    )
    
    # ===== 交易對和週期 =====
    parser.add_argument(
        "--symbols",
        default="BTCUSDT",
        help="交易對 (逗號分隔): BTCUSDT,ETHUSDT (default: BTCUSDT)"
    )
    
    parser.add_argument(
        "--interval",
        default="1h",
        help="K線週期 (逗號分隔): 1m,5m,15m,30m,1h,4h,1d,1w (default: 1h)"
    )
    
    # ===== 資金 =====
    parser.add_argument(
        "--capital",
        type=float,
        default=10000.0,
        help="初始資金 (default: 10000)"
    )
    
    # ===== 執行選項 =====
    parser.add_argument(
        "--once",
        action="store_true",
        help="只執行一次，不持續運行"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="顯示詳細輸出"
    )
    
    # ===== 數據下載選項 =====
    parser.add_argument(
        "--download",
        action="store_true",
        help="下載歷史數據後退出"
    )
    
    parser.add_argument(
        "--years",
        type=int,
        default=1,
        help="下載多少年的數據 (default: 1)"
    )
    
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="開始日期: YYYY-MM-DD"
    )
    
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="結束日期: YYYY-MM-DD"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="強制重新下載覆蓋現有數據"
    )
    
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=None,
        help="往回抓取多少天 (default: years * 365)"
    )
    
    # ===== 回測選項 =====
    parser.add_argument(
        "--backtest",
        action="store_true",
        help="執行回測模式"
    )
    
    parser.add_argument(
        "--backtest-start",
        type=str,
        default=None,
        help="回測開始日期: YYYY-MM-DD"
    )
    
    parser.add_argument(
        "--backtest-end",
        type=str,
        default=None,
        help="回測結束日期: YYYY-MM-DD"
    )
    
    parser.add_argument(
        "--require-full-data",
        action="store_true",
        help="回測範圍內缺數據時顯示錯誤"
    )
    
    # ===== 數據下載相關參數 =====
    parser.add_argument(
        "--rate-limit",
        type=int,
        default=10,
        help="下載時每分鐘請求次數 (default: 10)"
    )
    
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="下載時每批 K線數量 (default: 500)"
    )
    
    args = parser.parse_args()
    
    # 解析交易對和週期
    symbols = [s.strip().upper() for s in args.symbols.split(",")]
    intervals = [i.strip() for i in args.interval.split(",")]
    
    # 數據範圍
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    now_ms = int(now.timestamp() * 1000)
    
    # 防禦：如果 now_ms 小於合理值，嘗試用另一種方式獲取
    if now_ms < 1700000000000:  # 2023-10-01
        import time
        now_ms = int(time.time() * 1000)
        now = datetime.fromtimestamp(time.time(), tz=timezone.utc)
    
    print(f"   系統時間: {now} ({now_ms})")
    
    if args.end:
        end_date = datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        end_date = now
    
    if args.start:
        start_date = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        if args.lookback_days:
            start_date = end_date - timedelta(days=args.lookback_days)
        else:
            start_date = end_date - timedelta(days=args.years * 365)
    
    # 確保結束時間不超過現在
    if end_date.timestamp() * 1000 > now_ms:
        end_date = now
    
    # 確保開始時間不超過結束時間
    if start_date > end_date:
        start_date = end_date - timedelta(days=365)
    
    # 轉換為毫秒時間戳
    start_ts = int(start_date.timestamp() * 1000)
    end_ts = int(end_date.timestamp() * 1000)
    
    # 回測日期
    if args.backtest_start:
        backtest_start = datetime.strptime(args.backtest_start, "%Y-%m-%d")
    else:
        backtest_start = start_date
    
    if args.backtest_end:
        backtest_end = datetime.strptime(args.backtest_end, "%Y-%m-%d")
    else:
        backtest_end = end_date
    
    # 解析後立即處理下載模式，跳過多餘顯示
    if args.download or args.backtest:
        # 下載/回測模式不需要交易系統資訊
        pass
    else:
        # 環境檢查
        print("=" * 60)
        print("🤖 Multi-Agent Trading System")
        print("=" * 60)
        print(f"模式: {args.mode}")
        print(f"交易對: {symbols}")
        print(f"週期: {intervals}")
        print(f"數據範圍: {start_date.date()} ~ {end_date.date()}")
        print(f"初始資金: ${args.capital:,.2f}")
        
        if args.backtest:
            print(f"回測範圍: {backtest_start.date()} ~ {backtest_end.date()}")
        
        print("=" * 60)
    
    # 檢查 API Key
    if args.mode == "live":
        api_key = os.environ.get("BINANCE_API_KEY")
        if not api_key:
            print("❌ 錯誤: live 模式需要 BINANCE_API_KEY")
            print("   請設置環境變量: export BINANCE_API_KEY=your_key")
            sys.exit(1)
    
    # 檢查 OpenRouter
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    if not openrouter_key and args.verbose:
        print("⚠️ 警告: 未設置 OPENROUTER_API_KEY，LLM 功能將不可用")
    
    # 執行交易系統
    try:
        from agents import create_trading_system
        from data.binance import VALID_INTERVALS
        
        # 驗證週期
        for interval in intervals:
            if interval not in VALID_INTERVALS:
                print(f"❌ 不支援的週期: {interval}")
                print(f"   支援: {VALID_INTERVALS}")
                sys.exit(1)
        
        # ===== 數據下載模式 =====
        if args.download:
            print("\n📥 開始下載歷史數據...")
            print(f"   交易對: {symbols}")
            print(f"   週期: {intervals}")
            print(f"   範圍: {start_date.date()} ~ {end_date.date()}")
            print()
            
            try:
                from scripts.download_data import download_with_progress
                from data.binance import datetime_to_timestamp
            except ImportError as e:
                print(f"❌ 匯入錯誤: {e}")
                sys.exit(1)
            

            for symbol in symbols:
                for interval in intervals:
                    print(f"\n[{symbols.index(symbol)+1}/{len(symbols)}][{intervals.index(interval)+1}/{len(intervals)}] 下載: {symbol} {interval}")
                    
                    # 輸出目錄: data/{interval}/
                    output_dir = f"data/{interval}"
                    Path(output_dir).mkdir(exist_ok=True)
                    
                    # 檢查現有月份檔案
                    existing_files = list(Path(output_dir).glob(f"{symbol}_{interval}_*.csv"))
                    
                    # 合併所有月份檔案
                    existing_df = None
                    if existing_files and not args.force:
                        dfs = []
                        for f in existing_files:
                            df_month = pd.read_csv(f, parse_dates=['datetime'])
                            dfs.append(df_month)
                        if dfs:
                            existing_df = pd.concat(dfs, ignore_index=True)
                            existing_df = existing_df.drop_duplicates(subset=['datetime'], keep='first')
                            existing_df = existing_df.sort_values('datetime').reset_index(drop=True)
                    
                    # 如果數據存在，檢查日期範圍
                    if existing_df is not None and not existing_df.empty and not args.force:
                        existing_df['datetime'] = pd.to_datetime(existing_df['datetime'])
                        
                        # 確保時區是 tz-naive
                        if existing_df['datetime'].dt.tz is not None:
                            existing_df['datetime'] = existing_df['datetime'].dt.tz_localize(None)
                        
                        min_date = existing_df['datetime'].min()
                        max_date = existing_df['datetime'].max()
                        print(f"   ℹ️ 現有數據: {min_date.date()} ~ {max_date.date()} ({len(existing_df)} 筆)")
                        
                        # 轉換請求的時間範圍為 tz-naive
                        req_start = pd.to_datetime(start_ts, unit='ms')
                        req_end = pd.to_datetime(end_ts, unit='ms')
                        
                        # 如果現有數據已覆蓋請求範圍，則跳過
                        if min_date <= req_start and max_date >= req_end:
                            print(f"   ✅ 數據已完整，跳過下載")
                            continue
                        else:
                            # 計算需要補充的範圍
                            new_start = req_start if req_start < min_date else req_start
                            new_end = req_end if req_end > max_date else req_end
                            print(f"   ⚠️ 需要補充: {new_start.date()} ~ {new_end.date()}")
                            # 更新下載範圍
                            start_ts = int(new_start.timestamp() * 1000)
                            end_ts = int(new_end.timestamp() * 1000)
                    
                    try:
                        # 下載數據
                        df = download_with_progress(
                            symbol=symbol,
                            interval=interval,
                            start_time=start_ts,
                            end_time=end_ts,
                            rate_limit=args.rate_limit,
                            batch_size=args.batch_size,
                            save_callback=None,  # 不需要定期存檔
                        )
                        
                        if df is not None and not df.empty:
                            # 確保 datetime 是 tz-naive
                            df['datetime'] = pd.to_datetime(df['datetime'])
                            if df['datetime'].dt.tz is not None:
                                df['datetime'] = df['datetime'].dt.tz_localize(None)
                            
                            # 如果已有部分數據，合併
                            if existing_df is not None and not existing_df.empty:
                                print(f"   🔄 合併新舊數據...")
                                df = pd.concat([existing_df, df], ignore_index=True)
                                df = df.drop_duplicates(subset=['datetime'], keep='first')
                                df = df.sort_values('datetime').reset_index(drop=True)
                            
                            # 按月拆分存檔
                            df['yearmonth'] = df['datetime'].dt.strftime('%Y%m')
                            yearmonths = df['yearmonth'].unique()
                            
                            for ym in yearmonths:
                                mask = df['yearmonth'] == ym
                                df_month = df[mask].drop(columns=['yearmonth'])
                                output_file = f"{output_dir}/{symbol}_{interval}_{ym}.csv"
                                df_month.to_csv(output_file, index=False)
                                print(f"   ✅ 已存: {output_file} ({len(df_month)} 筆)")
                            
                            print(f"✅ 下載完成: {len(yearmonths)} 個月")
                        else:
                            print(f"⚠️ 無數據: {symbol} {interval}")
                    except Exception as e:
                        print(f"❌ 下載失敗: {e}")
                        import traceback
                        traceback.print_exc()
            
            print("\n✅ 下載完成!")
            sys.exit(0)
        
        # ===== 回測模式 =====
        if args.backtest:
            print("\n📈 執行回測模式...")
            
            # 檢查數據是否存在
            from scripts.download_data import download_with_progress
            from data.binance import datetime_to_timestamp
            
            for symbol in symbols:
                for interval in intervals:
                    data_file = Path(f"data/{symbol}_{interval}.parquet")
                    
                    if not data_file.exists():
                        if args.require_full_data:
                            print(f"❌ 錯誤: 缺少數據 {symbol} {interval}")
                            print(f"   請先下載: python scripts/run_trading_system.py --download --symbols {symbol} --interval {interval} --years 1")
                            sys.exit(1)
                        else:
                            print(f"⚠️ 警告: 缺少 {symbol} {interval}，正在下載...")
                            start_ts = datetime_to_timestamp(start_date)
                            end_ts = datetime_to_timestamp(end_date)
                            df = download_with_progress(symbol, interval, start_ts, end_ts, args.rate_limit, args.batch_size)
                            df.to_parquet(data_file, index=False)
                    
                    # 驗證數據範圍
                    df = pd.read_parquet(data_file)
                    df["datetime"] = pd.to_datetime(df["datetime"])
                    
                    min_date = df["datetime"].min()
                    max_date = df["datetime"].max()
                    
                    if backtest_start < min_date or backtest_end > max_date:
                        msg = f"⚠️ 數據範圍不足: {min_date} ~ {max_date}"
                        if args.require_full_data:
                            print(f"❌ {msg}")
                            print(f"   回測需要: {backtest_start} ~ {backtest_end}")
                            sys.exit(1)
                        else:
                            print(f"   {msg}")
            
            # TODO: 執行回測引擎
            print("✅ 數據驗證完成，回測引擎即將上線!")
            sys.exit(0)
        
        # ===== 即時交易模式 =====
        
        # 建立系統
        system = create_trading_system(
            symbols=symbols,
            intervals=intervals,
            initial_capital=args.capital,
            mode=args.mode,
        )
        
        if args.once:
            # 只執行一次
            print("\n🚀 執行一次交易流程...")
            result = system.run_once()
            print("\n結果:")
            for key, value in result.items():
                print(f"  {key}: {value.get('status', 'unknown')}")
        else:
            # 持續運行
            print("\n🚀 啟動交易系統 (持續運行)...")
            print("   按 Ctrl+C 停止\n")
            
            system.start()
            
            # 保持運行
            try:
                while True:
                    import time
                    time.sleep(60)
                    status = system.get_status()
                    if args.verbose:
                        print(f"📊 狀態: {status['cycles']} cycles, running: {status['running']}")
            except KeyboardInterrupt:
                print("\n\n🛑 停止交易系統...")
                system.stop()
        
        print("\n✅ 完成!")
        
    except ImportError as e:
        print(f"❌ 匯入錯誤: {e}")
        print("\n請先安裝依賴:")
        print("  pip install -r requirements.txt")
        sys.exit(1)
    
    except Exception as e:
        print(f"❌ 錯誤: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
