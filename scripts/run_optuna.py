#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Optuna Bayesian Optimization CLI

使用方式:
    python scripts/run_optuna.py --data data/BTCUSDT_1h.csv --trials 100
    python scripts/run_optuna.py --data data/BTCUSDT_1h.csv --short-low 5 --short-high 50 --long-low 20 --long-high 200 --trials 100
"""

import sys
import os
import argparse

# 確保可以匯入專案模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data import load_csv
from strategies import MACrossoverStrategy
from experiments import run_optuna_optimization


def main():
    parser = argparse.ArgumentParser(description="Optuna Bayesian Optimization for Strategy Parameters")
    parser.add_argument("--data", required=True, help="Path to CSV data file")
    parser.add_argument("--symbol", default="BTCUSDT", help="Trading symbol")
    parser.add_argument("--interval", default="1h", help="Time interval")
    
    # 參數空間
    parser.add_argument("--short-low", type=int, default=5, help="Short window low bound")
    parser.add_argument("--short-high", type=int, default=50, help="Short window high bound")
    parser.add_argument("--long-low", type=int, default=20, help="Long window low bound")
    parser.add_argument("--long-high", type=int, default=200, help="Long window high bound")
    
    # 優化選項
    parser.add_argument("--trials", type=int, default=100, help="Number of Optuna trials")
    parser.add_argument("--timeout", type=int, help="Timeout in seconds")
    parser.add_argument("--objective", default="sharpe_ratio",
                       choices=["sharpe_ratio", "total_return", "calmar_ratio", "sortino_ratio"],
                       help="Optimization objective")
    parser.add_argument("--direction", default="maximize",
                       choices=["maximize", "minimize"],
                       help="Optimization direction")
    
    # 資金和手續費
    parser.add_argument("--capital", type=float, default=10000.0, help="Initial capital")
    parser.add_argument("--commission", type=float, default=0.001, help="Commission rate")
    
    # 輸出
    parser.add_argument("--out", default="reports", help="Output directory")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🧠 Optuna 貝葉斯優化")
    print("=" * 60)
    
    # 建立參數空間
    param_space = {
        "short_window": {"low": args.short_low, "high": args.short_high, "type": "int"},
        "long_window": {"low": args.long_low, "high": args.long_high, "type": "int"},
    }
    
    print(f"\n📋 設定:")
    print(f"  資料: {args.data}")
    print(f"  Symbol: {args.symbol}")
    print(f"  Short Window: {args.short_low} ~ {args.short_high}")
    print(f"  Long Window: {args.long_low} ~ {args.long_high}")
    print(f"  試驗次數: {args.trials}")
    print(f"  目標: {args.objective}")
    print(f"  初始資金: ${args.capital:,.2f}")
    print(f"  手續費: {args.commission * 100}%")
    
    # 載入資料
    print(f"\n📂 載入資料...")
    data = load_csv(args.data)
    print(f"   資料筆數: {len(data)}")
    print(f"   日期範圍: {data['datetime'].min()} ~ {data['datetime'].max()}")
    
    # 執行優化
    print(f"\n🚀 開始 Optuna 優化...")
    result = run_optuna_optimization(
        data=data,
        strategy_class=MACrossoverStrategy,
        param_space=param_space,
        objective=args.objective,
        n_trials=args.trials,
        timeout=args.timeout,
        initial_capital=args.capital,
        commission_rate=args.commission,
        direction=args.direction,
        show_progress=True,
    )
    
    # 顯示結果
    print(f"\n{'=' * 60}")
    print(f"🏆 最佳結果")
    print(f"{'=' * 60}")
    print(f"  試驗次數: {result['n_trials']}")
    print(f"  最佳試驗: #{result['best_trial']}")
    print(f"  最佳 {args.objective}: {result['best_value']:.4f}")
    print(f"  最佳參數:")
    for k, v in result['best_params'].items():
        print(f"    {k}: {v}")
    
    print(f"\n📊 最終回測指標:")
    metrics = result['final_metrics']
    print(f"  總報酬: {metrics['total_return']*100:.2f}%")
    print(f"  年化報酬: {metrics['annualized_return']*100:.2f}%")
    print(f"  最大回撤: {metrics['max_drawdown']*100:.2f}%")
    print(f"  Sharpe: {metrics['sharpe_ratio']:.2f}")
    print(f"  Sortino: {metrics['sortino_ratio']:.2f}")
    print(f"  Calmar: {metrics['calmar_ratio']:.2f}")
    print(f"  總交易次: {metrics['total_trades']}")
    print(f"  勝率: {metrics['win_rate']*100:.2f}%")
    
    # 儲存結果
    os.makedirs(args.out, exist_ok=True)
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    
    # 儲存 trials 歷史
    trials_data = []
    for trial in result['study'].trials:
        row = {
            "trial_number": trial.number,
            "state": trial.state.name,
            "value": trial.value,
            **trial.params,
        }
        trials_data.append(row)
    
    trials_df = pd.DataFrame(trials_data)
    trials_path = os.path.join(args.out, f"optuna_trials_{args.symbol}_{args.interval}_{timestamp}.csv")
    trials_df.to_csv(trials_path, index=False)
    print(f"\n📝 試驗歷史已儲存至: {trials_path}")
    
    # Markdown 報告
    md_path = os.path.join(args.out, f"optuna_report_{args.symbol}_{args.interval}_{timestamp}.md")
    with open(md_path, "w") as f:
        f.write(f"# 🧠 Optuna 貝葉斯優化結果\n\n")
        f.write(f"**Symbol**: {args.symbol}\n\n")
        f.write(f"**Interval**: {args.interval}\n\n")
        f.write(f"**目標**: {args.objective}\n\n")
        f.write(f"**試驗次數**: {result['n_trials']}\n\n")
        
        f.write(f"## 最佳參數\n\n")
        for k, v in result['best_params'].items():
            f.write(f"- **{k}**: {v}\n")
        
        f.write(f"\n## 最終回測指標\n\n")
        f.write(f"| 指標 | 數值 |\n")
        f.write(f"|------|------|\n")
        f.write(f"| 總報酬 | {metrics['total_return']*100:.2f}% |\n")
        f.write(f"| 年化報酬 | {metrics['annualized_return']*100:.2f}% |\n")
        f.write(f"| 最大回撤 | {metrics['max_drawdown']*100:.2f}% |\n")
        f.write(f"| Sharpe | {metrics['sharpe_ratio']:.2f} |\n")
        f.write(f"| Sortino | {metrics['sortino_ratio']:.2f} |\n")
        f.write(f"| Calmar | {metrics['calmar_ratio']:.2f} |\n")
        f.write(f"| 總交易次 | {metrics['total_trades']} |\n")
        f.write(f"| 勝率 | {metrics['win_rate']*100:.2f}% |\n")
        
        f.write(f"\n## 試驗歷史 (Top 20)\n\n")
        top_trials = trials_df.dropna(subset=['value']).sort_values('value', ascending=False).head(20)
        f.write(top_trials.to_markdown(index=False))
    
    print(f"📝 報告已儲存至: {md_path}")
    
    print(f"\n✅ 完成!")


if __name__ == "__main__":
    import pandas as pd
    main()
