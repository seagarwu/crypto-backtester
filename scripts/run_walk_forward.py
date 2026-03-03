#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Walk-Forward Testing CLI

使用方式:
    python scripts/run_walk_forward.py --data data/BTCUSDT_1h.csv --train-bars 2000 --test-bars 500
"""

import sys
import os
import argparse

# 確保可以匯入專案模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data import load_csv
from strategies import MACrossoverStrategy
from experiments import run_walk_forward


def parse_range(s: str) -> list:
    """解析範圍字串"""
    if ":" in s:
        parts = s.split(":")
        if len(parts) == 3:
            start, end, step = int(parts[0]), int(parts[1]), int(parts[2])
            return list(range(start, end + 1, step))
    return [int(x) for x in s.split(",")]


def main():
    parser = argparse.ArgumentParser(description="Walk-Forward Testing")
    parser.add_argument("--data", required=True, help="Path to CSV data file")
    parser.add_argument("--symbol", default="BTCUSDT", help="Trading symbol")
    parser.add_argument("--interval", default="1h", help="Time interval")
    parser.add_argument("--train-bars", type=int, required=True, help="Training period in bars")
    parser.add_argument("--test-bars", type=int, required=True, help="Testing period in bars")
    parser.add_argument("--step-bars", type=int, help="Step size (default: same as test-bars)")
    parser.add_argument("--short", default="10,20,30", help="Short window range")
    parser.add_argument("--long", default="50,100", help="Long window range")
    parser.add_argument("--capital", type=float, default=10000.0, help="Initial capital")
    parser.add_argument("--commission", type=float, default=0.001, help="Commission rate")
    parser.add_argument("--score", default="sharpe_ratio", 
                       choices=["sharpe_ratio", "total_return", "calmar_ratio"],
                       help="Scoring metric for parameter selection")
    parser.add_argument("--out", default="reports", help="Output directory")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🔄 Walk-Forward Testing")
    print("=" * 60)
    
    # 解析參數範圍
    short_windows = parse_range(args.short)
    long_windows = parse_range(args.long)
    
    print(f"\n📋 設定:")
    print(f"  資料: {args.data}")
    print(f"  Symbol: {args.symbol}")
    print(f"  Train: {args.train_bars} bars")
    print(f"  Test: {args.test_bars} bars")
    print(f"  Step: {args.step_bars or args.test_bars} bars")
    print(f"  Short Windows: {short_windows}")
    print(f"  Long Windows: {long_windows}")
    print(f"  評分標準: {args.score}")
    
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
    
    # 執行 Walk-forward
    print(f"\n🚀 開始 Walk-Forward Testing...")
    result = run_walk_forward(
        data=data,
        strategy_class=MACrossoverStrategy,
        param_ranges=param_ranges,
        train_bars=args.train_bars,
        test_bars=args.test_bars,
        step_bars=args.step_bars,
        initial_capital=args.capital,
        commission_rate=args.commission,
        scoring=args.score,
    )
    
    folds_df = result["folds_results"]
    stitched_equity = result["stitched_equity"]
    summary = result["summary"]
    
    # 顯示結果
    print(f"\n{'='*60}")
    print("📊 Fold 結果")
    print(f"{'='*60}")
    print(folds_df.to_string(index=False))
    
    print(f"\n{'='*60}")
    print("📈 整體統計")
    print(f"{'='*60}")
    print(f"  總 Fold 數: {summary['total_folds']}")
    print(f"  平均測試報酬: {summary['avg_test_return']*100:.2f}%")
    print(f"  平均 Sharpe: {summary['avg_test_sharpe']:.2f}")
    print(f"  平均回撤: {summary['avg_test_drawdown']*100:.2f}%")
    print(f"  累積報酬: {summary['cumulative_return']*100:.2f}%")
    
    # 儲存結果
    os.makedirs(args.out, exist_ok=True)
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    
    # CSV
    folds_path = os.path.join(args.out, f"walkforward_folds_{args.symbol}_{args.interval}_{timestamp}.csv")
    folds_df.to_csv(folds_path, index=False)
    print(f"\n📝 Fold 結果已儲存至: {folds_path}")
    
    equity_path = os.path.join(args.out, f"walkforward_equity_{args.symbol}_{args.interval}_{timestamp}.csv")
    stitched_equity.to_csv(equity_path, index=False)
    print(f"📝 Equity Curve 已儲存至: {equity_path}")
    
    # Markdown 報告
    md_path = os.path.join(args.out, f"walkforward_report_{args.symbol}_{args.interval}_{timestamp}.md")
    with open(md_path, "w") as f:
        f.write(f"# 🔄 Walk-Forward Testing 報告\n\n")
        f.write(f"**Symbol**: {args.symbol}\n\n")
        f.write(f"**Interval**: {args.interval}\n\n")
        f.write(f"**Train**: {args.train_bars} bars\n\n")
        f.write(f"**Test**: {args.test_bars} bars\n\n")
        f.write(f"**評分標準**: {args.score}\n\n")
        
        f.write(f"## 整體統計\n\n")
        f.write(f"| 指標 | 數值 |\n")
        f.write(f"|------|------|\n")
        f.write(f"| 總 Fold 數 | {summary['total_folds']} |\n")
        f.write(f"| 平均測試報酬 | {summary['avg_test_return']*100:.2f}% |\n")
        f.write(f"| 平均 Sharpe | {summary['avg_test_sharpe']:.2f} |\n")
        f.write(f"| 平均回撤 | {summary['avg_test_drawdown']*100:.2f}% |\n")
        f.write(f"| 累積報酬 | {summary['cumulative_return']*100:.2f}% |\n")
        
        f.write(f"\n## Fold 結果\n\n")
        f.write(folds_df.to_markdown(index=False))
    print(f"📝 報告已儲存至: {md_path}")
    
    print(f"\n✅ 完成!")


if __name__ == "__main__":
    import pandas as pd
    main()
