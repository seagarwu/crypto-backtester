#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Grid Search CLI

使用方式:
    python scripts/run_grid_search.py --data data/BTCUSDT_1h.csv --short 10,20,30 --long 50,100 --out reports/
"""

import sys
import os
import argparse

# 確保可以匯入專案模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data import load_csv
from strategies import MACrossoverStrategy
from experiments import run_grid_search, select_top_k
from metrics import print_metrics


def parse_range(s: str) -> list:
    """解析範圍字串，如 '10,20,30' 或 '10:51:10'"""
    if ":" in s:
        parts = s.split(":")
        if len(parts) == 3:
            start, end, step = int(parts[0]), int(parts[1]), int(parts[2])
            return list(range(start, end + 1, step))
    return [int(x) for x in s.split(",")]


def main():
    parser = argparse.ArgumentParser(description="Grid Search for Strategy Parameters")
    parser.add_argument("--data", required=True, help="Path to CSV data file")
    parser.add_argument("--symbol", default="BTCUSDT", help="Trading symbol")
    parser.add_argument("--interval", default="1h", help="Time interval")
    parser.add_argument("--short", required=True, help="Short window range (e.g., '10,20,30' or '10:51:10')")
    parser.add_argument("--long", required=True, help="Long window range (e.g., '50,100,200' or '50:101:10')")
    parser.add_argument("--capital", type=float, default=10000.0, help="Initial capital")
    parser.add_argument("--commission", type=float, default=0.001, help="Commission rate")
    parser.add_argument("--score", default="sharpe_ratio", 
                       choices=["sharpe_ratio", "total_return", "calmar_ratio", "win_rate"],
                       help="Scoring metric")
    parser.add_argument("--top-k", type=int, default=10, help="Number of top results to show")
    parser.add_argument("--out", default="reports", help="Output directory")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🔍 參數網格掃描 (Grid Search)")
    print("=" * 60)
    
    # 解析參數範圍
    short_windows = parse_range(args.short)
    long_windows = parse_range(args.long)
    
    print(f"\n📋 設定:")
    print(f"  資料: {args.data}")
    print(f"  Symbol: {args.symbol}")
    print(f"  Short Windows: {short_windows}")
    print(f"  Long Windows: {long_windows}")
    print(f"  初始資金: ${args.capital:,.2f}")
    print(f"  手續費: {args.commission * 100}%")
    print(f"  評分標準: {args.score}")
    
    # 檢查 short < long
    invalid_combos = [(s, l) for s in short_windows for l in long_windows if s >= l]
    if invalid_combos:
        print(f"\n⚠️  警告: 將排除 {len(invalid_combos)} 個 short >= long 的組合")
    
    # 載入資料
    print(f"\n📂 載入資料...")
    data = load_csv(args.data)
    print(f"   資料筆數: {len(data)}")
    print(f"   日期範圍: {data['datetime'].min()} ~ {data['datetime'].max()}")
    
    # 建立參數網格
    param_ranges = {
        "short_window": short_windows,
        "long_window": long_windows,
    }
    
    # 執行網格掃描
    print(f"\n🚀 開始網格掃描...")
    results = run_grid_search(
        data=data,
        strategy_class=MACrossoverStrategy,
        param_ranges=param_ranges,
        initial_capital=args.capital,
        commission_rate=args.commission,
        scoring=args.score,
    )
    
    # 取得 Top K
    top_k = select_top_k(results, k=args.top_k, by=args.score)
    
    # 顯示結果
    print(f"\n{'=' * 60}")
    print(f"🏆 Top {args.top_k} 結果 (按 {args.score} 排序)")
    print(f"{'=' * 60}")
    print(top_k.to_string(index=False))
    
    # 儲存結果
    os.makedirs(args.out, exist_ok=True)
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    
    # CSV
    csv_path = os.path.join(args.out, f"grid_search_{args.symbol}_{args.interval}_{timestamp}.csv")
    results.to_csv(csv_path, index=False)
    print(f"\n📝 結果已儲存至: {csv_path}")
    
    # Markdown 報告
    md_path = os.path.join(args.out, f"grid_search_{args.symbol}_{args.interval}_{timestamp}.md")
    with open(md_path, "w") as f:
        f.write(f"# 🔍 Grid Search 結果\n\n")
        f.write(f"**Symbol**: {args.symbol}\n\n")
        f.write(f"**Interval**: {args.interval}\n\n")
        f.write(f"**評分標準**: {args.score}\n\n")
        f.write(f"## Top {args.top_k}\n\n")
        f.write(top_k.to_markdown(index=False))
    print(f"📝 報告已儲存至: {md_path}")
    
    print(f"\n✅ 完成!")


if __name__ == "__main__":
    import pandas as pd
    main()
