#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
數據重組腳本 - 將單一檔案按年月拆分

使用方法:
    python scripts/reorganize_data.py

輸入:
    data/BTCUSDT_1m.csv  (或其他週期)
    
輸出:
    data/1m/BTCUSDT_1m_201605.csv
    data/1m/BTCUSDT_1m_202512.csv
    ...
"""

import os
import sys
import glob
from pathlib import Path

# 確保可以匯入專案模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd


def reorganize_file(input_path: str, dry_run: bool = True) -> int:
    """
    將一個大檔案按年月拆分
    
    Args:
        input_path: 輸入檔案路徑 (如 data/BTCUSDT_1m.csv)
        dry_run: True = 只顯示會做什麼，不實際執行
        
    Returns:
        輸出的檔案數量
    """
    filename = os.path.basename(input_path)
    
    # 解析檔名: BTCUSDT_1m.csv -> symbol=BTCUSDT, interval=1m
    parts = filename.replace('.csv', '').split('_')
    if len(parts) != 2:
        print(f"  ⚠️  無法解析檔名: {filename}, 跳過")
        return 0
    
    symbol = parts[0]
    interval = parts[1]
    
    print(f"\n📂 處理: {filename}")
    print(f"   Symbol: {symbol}, Interval: {interval}")
    
    # 建立輸出目錄
    output_dir = os.path.join(os.path.dirname(input_path), interval)
    if not dry_run:
        os.makedirs(output_dir, exist_ok=True)
    else:
        print(f"   → 輸出目錄: {output_dir}/")
    
    # 讀取資料
    print(f"   載入資料...")
    df = pd.read_csv(input_path)
    
    # 確保 datetime 欄位存在
    if 'datetime' not in df.columns:
        print(f"   ⚠️  沒有 datetime 欄位，跳過")
        return 0
    
    # 轉換datetime
    df['datetime'] = pd.to_datetime(df['datetime'])
    
    # 取得年月
    df['yearmonth'] = df['datetime'].dt.strftime('%Y%m')
    
    # 按年月分組
    yearmonths = sorted(df['yearmonth'].unique())
    print(f"   資料範圍: {df['datetime'].min()} ~ {df['datetime'].max()}")
    print(f"   共 {len(yearmonths)} 個月: {yearmonths[0]} ~ {yearmonths[-1]}")
    
    # 拆分並儲存
    output_count = 0
    for ym in yearmonths:
        mask = df['yearmonth'] == ym
        subset = df[mask].drop(columns=['yearmonth'])
        
        output_filename = f"{symbol}_{interval}_{ym}.csv"
        output_path = os.path.join(output_dir, output_filename)
        
        if dry_run:
            count = mask.sum()
            print(f"   → {output_filename}: {count} rows")
        else:
            subset.to_csv(output_path, index=False)
            print(f"   ✅ 儲存: {output_filename}")
        
        output_count += 1
    
    return output_count


def main():
    print("=" * 60)
    print("🔄 數據重組腳本")
    print("   將單一檔案按年月拆分")
    print("=" * 60)
    
    # 找出所有 CSV 檔案
    data_dir = "data"
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    
    if not csv_files:
        print(f"\n⚠️  在 {data_dir}/ 找不到 CSV 檔案")
        return
    
    print(f"\n找到 {len(csv_files)} 個 CSV 檔案:")
    for f in csv_files:
        size_mb = os.path.getsize(f) / (1024 * 1024)
        print(f"  - {os.path.basename(f)} ({size_mb:.1f} MB)")
    
    # 先做 dry-run 顯示會做什麼
    print("\n" + "=" * 60)
    print("🔍 Dry Run - 預覽將執行的操作:")
    print("=" * 60)
    
    total_outputs = 0
    for csv_file in csv_files:
        count = reorganize_file(csv_file, dry_run=True)
        total_outputs += count
    
    print(f"\n📊 總共會產生 {total_outputs} 個月度檔案")
    
    # 確認是否執行
    print("\n" + "=" * 60)
    response = input("確認執行? (y/n): ").strip().lower()
    
    if response == 'y':
        print("\n🚀 開始執行...")
        for csv_file in csv_files:
            reorganize_file(csv_file, dry_run=False)
        print("\n✅ 完成!")
    else:
        print("\n❌ 已取消")


if __name__ == "__main__":
    main()
