#!/usr/bin/env python3
"""
數據下載腳本 - Download Historical Data

使用方式:
    python scripts/download_data.py --symbols BTCUSDT --interval 1h --years 10
    python scripts/download_data.py --symbols BTCUSDT ETHUSDT --interval 1h,1d --years 5
    python scripts/download_data.py --start-date 2020-01-01 --end-date 2025-12-31
"""

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

import pandas as pd

# 確保可以匯入模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.binance import (
    download_klines_range,
    datetime_to_timestamp,
    parse_interval_to_ms,
    VALID_INTERVALS,
)


def parse_intervals(intervals_str: str) -> List[str]:
    """解析週期字串"""
    intervals = []
    for i in intervals_str.split(","):
        i = i.strip()
        if i not in VALID_INTERVALS:
            raise ValueError(f"不支援的週期: {i}. 支援: {VALID_INTERVALS}")
        intervals.append(i)
    return intervals


def parse_symbols(symbols_str: str) -> List[str]:
    """解析交易對字串"""
    return [s.strip().upper() for s in symbols_str.split(",")]


def format_duration(seconds: int) -> str:
    """格式化時間"""
    if seconds < 60:
        return f"{seconds}秒"
    elif seconds < 3600:
        return f"{seconds/60:.1f}分鐘"
    elif seconds < 86400:
        return f"{seconds/3600:.1f}小時"
    else:
        return f"{seconds/86400:.1f}天"


def download_with_progress(
    symbol: str,
    interval: str,
    start_time: int,
    end_time: int,
    rate_limit: int = 10,
    batch_size: int = 500,
) -> pd.DataFrame:
    """
    帶進度顯示的下載函數
    
    Args:
        symbol: 交易對
        interval: K線週期
        start_time: 開始時間戳 (UTC, 毫秒)
        end_time: 結束時間戳 (UTC, 毫秒)
        rate_limit: 每分鐘請求次數
        batch_size: 每批數據量
    
    Returns:
        DataFrame
    """
    from time import sleep
    
    from datetime import datetime, timezone
    
    # 如果開始時間是大於現在，說明計算錯誤
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    if start_time > now_ms:
        print(f"   ⚠️ 開始時間 {pd.to_datetime(start_time, unit='ms')} 是未來時間，調整為現在")
        start_time = now_ms - (365 * 24 * 3600 * 1000)  # 最近 1 年
    
    if end_time > now_ms:
        end_time = now_ms
    
    interval_ms = parse_interval_to_ms(interval)
    
    # 計算總共需要多少批 (每批 batch_size 根 K 線)
    total_ms = end_time - start_time
    if total_ms <= 0:
        print(f"   ⚠️ 無效的時間範圍")
        return pd.DataFrame()
    
    estimated_batches = max(1, total_ms // (interval_ms * batch_size))
    
    print(f"\n📊 {symbol} {interval}:")
    print(f"   時間範圍: {pd.to_datetime(start_time, unit='ms')} ~ {pd.to_datetime(end_time, unit='ms')}")
    print(f"   估計需要: {estimated_batches} 批次")
    print(f"   速率限制: {rate_limit} 次/分鐘")
    
    all_data = []
    current_start = start_time
    batch_num = 0
    total_rows = 0
    request_count = 0
    start_time_real = datetime.now(timezone.utc)
    
    while current_start < end_time:
        batch_num += 1
        
        # 如果這批時間已經是未來，就停止
        if current_start >= now_ms:
            print(f"   ⚠️ 已到達現在時間，下載完成")
            break
        
        try:
            # 直接調用 Binance API
            from data.binance import DataDownloader
            downloader = DataDownloader()
            
            # 這批請求的結束時間
            request_end = min(current_start + interval_ms * batch_size, end_time, now_ms)
            
            df = downloader.download_klines(
                symbol=symbol,
                interval=interval,
                start_time=current_start,
                limit=min(batch_size, 1000),  # Binance 最多 1000
            )
            
            request_count += 1
            
            if df is None or df.empty:
                print(f"   ⚠️ 批次 {batch_num}: 無更多數據")
                break
            
            all_data.append(df)
            total_rows += len(df)
            
            # 進度計算
            progress = min(100, (current_start - start_time) / total_ms * 100)
            elapsed = (datetime.now(timezone.utc) - start_time_real).total_seconds()
            
            print(f"   批次 {batch_num}: +{len(df)} 筆 | 進度: {progress:.1f}% | 已用時: {format_duration(int(elapsed))}")
            
            # 取得下一批的開始時間 (最後一根 K 線的時間 + 1 根)
            last_time = int(pd.Timestamp(df["datetime"].iloc[-1]).timestamp() * 1000)
            current_start = last_time + interval_ms
            
        except Exception as e:
            print(f"   ❌ 批次 {batch_num} 失敗: {e}")
            import traceback
            traceback.print_exc()
            sleep(5)  # 失敗後等待
            continue
        
        # 速率限制
        if request_count >= rate_limit:
            sleep(60 / rate_limit)  # 每分鐘 rate_limit 次
    
    if not all_data:
        return pd.DataFrame()
    
    # 合併
    combined = pd.concat(all_data, ignore_index=True)
    combined = combined.drop_duplicates(subset=["datetime"], keep="first")
    combined = combined.sort_values("datetime").reset_index(drop=True)
    
    elapsed = (datetime.now(timezone.utc) - start_time_real).total_seconds()
    print(f"   ✅ 完成: {len(combined)} 筆 | 總用時: {format_duration(int(elapsed))} | 平均速率: {request_count/elapsed*60:.1f} 次/分鐘")
    
    return combined


def main():
    parser = argparse.ArgumentParser(
        description="下載 Binance 歷史 K 線數據",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  python scripts/download_data.py --symbols BTCUSDT --interval 1h --years 10
  python scripts/download_data.py --symbols BTCUSDT,ETHUSDT --interval 1h,1d --years 5
  python scripts/download_data.py --symbols BTCUSDT --start 2020-01-01 --end 2025-12-31
  python scripts/download_data.py --symbols BTCUSDT --interval 15m --years 1 --force
        """
    )
    
    parser.add_argument(
        "--symbols", "-s",
        default="BTCUSDT",
        help="交易對 (逗號分隔): BTCUSDT,ETHUSDT (default: BTCUSDT)"
    )
    
    parser.add_argument(
        "--interval", "-i",
        default="1h",
        help="K線週期 (逗號分隔): 1m,5m,15m,30m,1h,4h,1d,1w (default: 1h)"
    )
    
    parser.add_argument(
        "--years", "-y",
        type=int,
        default=1,
        help="下載多少年的數據 (default: 1)"
    )
    
    parser.add_argument(
        "--start", "-st",
        type=str,
        default=None,
        help="開始日期: YYYY-MM-DD (預設: 現在往前 N 年)"
    )
    
    parser.add_argument(
        "--end", "-en",
        type=str,
        default=None,
        help="結束日期: YYYY-MM-DD (預設: 現在)"
    )
    
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="強制重新下載 (覆蓋現有數據)"
    )
    
    parser.add_argument(
        "--rate-limit",
        type=int,
        default=10,
        help="每分鐘請求次數 (default: 10)"
    )
    
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="每批請求的 K線數量 (default: 500)"
    )
    
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="data",
        help="輸出目錄 (default: data)"
    )
    
    args = parser.parse_args()
    
    # 解析參數
    symbols = parse_symbols(args.symbols)
    intervals = parse_intervals(args.interval)
    
    # 計算時間範圍
    now = datetime.now()
    if args.end:
        end_dt = datetime.strptime(args.end, "%Y-%m-%d")
    else:
        end_dt = now
    
    if args.start:
        start_dt = datetime.strptime(args.start, "%Y-%m-%d")
    else:
        start_dt = end_dt - timedelta(days=args.years * 365)
    
    print("=" * 60)
    print("📥 Binance 歷史數據下載器")
    print("=" * 60)
    print(f"交易對: {symbols}")
    print(f"週期: {intervals}")
    print(f"時間範圍: {start_dt.date()} ~ {end_dt.date()}")
    print(f"輸出目錄: {args.output}")
    print(f"速率限制: {args.rate_limit} 次/分鐘")
    print("=" * 60)
    
    # 確保輸出目錄存在
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 計算總任務數
    total_tasks = len(symbols) * len(intervals)
    current_task = 0
    
    # 下載數據
    for symbol in symbols:
        for interval in intervals:
            current_task += 1
            print(f"\n[{current_task}/{total_tasks}] 開始下載...")
            
            # 輸出檔案路徑
            output_file = output_dir / f"{symbol}_{interval}.parquet"
            csv_file = output_dir / f"{symbol}_{interval}.csv"
            
            # 檢查現有數據
            if not args.force:
                if output_file.exists():
                    existing = pd.read_parquet(output_file)
                    print(f"   ⚠️ 數據已存在: {output_file} ({len(existing)} 筆)")
                    print(f"   請使用 --force 強制重新下載")
                    continue
                if csv_file.exists():
                    existing = pd.read_csv(csv_file, parse_dates=["datetime"])
                    print(f"   ⚠️ 數據已存在: {csv_file} ({len(existing)} 筆)")
                    print(f"   請使用 --force 強制重新下載")
                    continue
            
            # 下載
            start_ts = datetime_to_timestamp(start_dt)
            end_ts = datetime_to_timestamp(end_dt)
            
            df = download_with_progress(
                symbol=symbol,
                interval=interval,
                start_time=start_ts,
                end_time=end_ts,
                rate_limit=args.rate_limit,
                batch_size=args.batch_size,
            )
            
            if df.empty:
                print(f"   ❌ 無法下載數據")
                continue
            
            # 儲存
            print(f"   💾 儲存數據...")
            
            # 先存 Parquet (更快)
            df.to_parquet(output_file, index=False)
            print(f"      已存: {output_file}")
            
            # 也存 CSV (相容性)
            df.to_csv(csv_file, index=False)
            print(f"      已存: {csv_file}")
    
    print("\n" + "=" * 60)
    print("✅ 下載完成!")
    print("=" * 60)
    
    # 顯示統計
    print("\n📊 下載統計:")
    for symbol in symbols:
        for interval in intervals:
            parquet_file = output_dir / f"{symbol}_{interval}.parquet"
            csv_file = output_dir / f"{symbol}_{interval}.csv"
            
            if parquet_file.exists():
                df = pd.read_parquet(parquet_file)
                print(f"   {symbol} {interval}: {len(df)} 筆 ({df['datetime'].min()} ~ {df['datetime'].max()})")
            elif csv_file.exists():
                df = pd.read_csv(csv_file, parse_dates=["datetime"])
                print(f"   {symbol} {interval}: {len(df)} 筆 ({df['datetime'].min()} ~ {df['datetime'].max()})")


if __name__ == "__main__":
    main()
