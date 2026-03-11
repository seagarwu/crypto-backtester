"""
報告生成模組

生成回測和優化結果的視覺化報告。
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np

# 嘗試導入繪圖庫
try:
    import matplotlib
    import matplotlib.pyplot as plt
    import seaborn as sns
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


class ReportGenerator:
    """回測報告生成器"""
    
    def __init__(self, output_dir: str = "reports"):
        """
        初始化報告生成器
        
        Args:
            output_dir: 輸出目錄
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        if MATPLOTLIB_AVAILABLE:
            # 設定樣式
            plt.style.use('seaborn-v0_8-whitegrid')
            sns.set_palette("husl")
    
    def plot_equity_curve(
        self,
        equity_df: pd.DataFrame,
        title: str = "Equity Curve",
        filename: Optional[str] = None,
    ) -> Optional[str]:
        """
        繪製資金曲線
        
        Args:
            equity_df: 包含 datetime 和 equity 欄位的 DataFrame
            title: 圖表標題
            filename: 輸出檔名
            
        Returns:
            輸出檔案路徑
        """
        if not MATPLOTLIB_AVAILABLE:
            print("⚠️ matplotlib 未安裝，跳過繪圖")
            return None
        
        # Handle empty or invalid data
        if equity_df is None or equity_df.empty:
            print("⚠️ 無效的 equity 數據，跳過繪圖")
            return None
        
        if 'datetime' not in equity_df.columns or 'equity' not in equity_df.columns:
            print("⚠️ 缺少必要欄位，跳過繪圖")
            return None
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        ax.plot(equity_df['datetime'], equity_df['equity'], linewidth=1.5, label='Equity')
        ax.fill_between(equity_df['datetime'], equity_df['equity'], alpha=0.3)
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Equity ($)', fontsize=12)
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # 格式化 y 軸
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
        
        plt.tight_layout()
        
        if filename is None:
            filename = f"equity_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.png"
        
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()
        
        return str(filepath)
    
    def plot_drawdown(
        self,
        equity_df: pd.DataFrame,
        title: str = "Drawdown",
        filename: Optional[str] = None,
    ) -> Optional[str]:
        """
        繪製回撤曲線
        
        Args:
            equity_df: 包含 datetime 和 equity 欄位的 DataFrame
            title: 圖表標題
            filename: 輸出檔名
            
        Returns:
            輸出檔案路徑
        """
        if not MATPLOTLIB_AVAILABLE:
            return None
        
        # 計算回撤
        equity = equity_df['equity']
        running_max = equity.cummax()
        drawdown = (equity - running_max) / running_max
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        ax.fill_between(equity_df['datetime'], drawdown, 0, 
                       alpha=0.3, color='red', label='Drawdown')
        ax.plot(equity_df['datetime'], drawdown, color='red', linewidth=1)
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Drawdown', fontsize=12)
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # 格式化 y 軸為百分比
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x*100:.0f}%'))
        
        plt.tight_layout()
        
        if filename is None:
            filename = f"drawdown_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.png"
        
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()
        
        return str(filepath)
    
    def plot_trades(
        self,
        trades_df: pd.DataFrame,
        price_df: pd.DataFrame,
        title: str = "Trades",
        filename: Optional[str] = None,
    ) -> Optional[str]:
        """
        繪製交易点位圖（簡單版）
        
        Args:
            trades_df: 交易記錄
            price_df: 價格數據
            title: 圖表標題
            filename: 輸出檔名
            
        Returns:
            輸出檔案路徑
        """
        if not MATPLOTLIB_AVAILABLE:
            return None
        
        fig, ax = plt.subplots(figsize=(14, 7))
        
        # 繪製價格
        ax.plot(price_df['datetime'], price_df['close'], 
               linewidth=1, color='black', alpha=0.7, label='Close Price')
        
        # 繪製買入賣出點
        for _, trade in trades_df.iterrows():
            if trade.get('direction', 'long') == 'long':
                color = 'green' if trade.get('pnl', 0) >= 0 else 'red'
                marker = '^' if trade.get('side') == 'buy' else 'v'
            else:
                color = 'red' if trade.get('pnl', 0) >= 0 else 'green'
                marker = 'v' if trade.get('side') == 'buy' else '^'
            
            #  entry
            ax.scatter(trade['entry_time'], trade['entry_price'], 
                      marker=marker, s=100, color=color, zorder=5)
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Price ($)', fontsize=12)
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if filename is None:
            filename = f"trades_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.png"
        
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()
        
        return str(filepath)
    
    def plot_trades_with_indicators(
        self,
        trades_df: pd.DataFrame,
        price_df: pd.DataFrame,
        title: str = "Trades with Technical Indicators",
        filename: Optional[str] = None,
        ma_periods: List[int] = None,
        bband_period: int = 20,
        bband_std: float = 2.0,
    ) -> Optional[str]:
        """
        繪製交易點位圖（含技術指標）
        
        Args:
            trades_df: 交易記錄
            price_df: 價格數據
            title: 圖表標題
            filename: 輸出檔名
            ma_periods: MA 週期列表 (預設 [20, 50, 200])
            bband_period: BBand 週期 (預設 20)
            bband_std: BBand 標準差倍數 (預設 2.0)
            
        Returns:
            輸出檔案路徑
        """
        if not MATPLOTLIB_AVAILABLE:
            return None
        
        # 確保數據足夠
        if len(price_df) < bband_period:
            # 數據不足，只畫價格和買賣點
            return self.plot_trades(trades_df, price_df, title, filename)
        
        # 預設 MA 週期
        ma_periods = ma_periods or [20, 50, 200]
        
        # 複製數據避免修改原數據
        df = price_df.copy()
        
        # 計算 MA
        for period in ma_periods:
            df[f'MA_{period}'] = df['close'].rolling(window=period).mean()
        
        # 計算 BBand
        df['BB_middle'] = df['close'].rolling(window=bband_period).mean()
        bb_std = df['close'].rolling(window=bband_period).std()
        df['BB_upper'] = df['BB_middle'] + (bb_std * bband_std)
        df['BB_lower'] = df['BB_middle'] - (bb_std * bband_std)
        
        # 創建圖表（主圖 + 成交量）
        fig = plt.figure(figsize=(16, 10))
        
        # 主圖：價格 + MA + BBand
        ax1 = plt.subplot2grid((3, 1), (0, 0), rowspan=2)
        
        # 繪製 BBand
        ax1.fill_between(df['datetime'], df['BB_upper'], df['BB_lower'], 
                        alpha=0.1, color='blue', label='Bollinger Bands')
        ax1.plot(df['datetime'], df['BB_upper'], 
                linewidth=0.5, color='blue', alpha=0.5, linestyle='--')
        ax1.plot(df['datetime'], df['BB_lower'], 
                linewidth=0.5, color='blue', alpha=0.5, linestyle='--')
        
        # 繪製 MA
        colors = ['orange', 'green', 'red']
        for i, period in enumerate(ma_periods):
            if period <= df.index[-1] + 1:  # 確保 MA 週期在數據範圍內
                ax1.plot(df['datetime'], df[f'MA_{period}'], 
                        linewidth=1.5, color=colors[i % len(colors)], 
                        label=f'MA {period}', alpha=0.8)
        
        # 繪製價格
        ax1.plot(df['datetime'], df['close'], 
                linewidth=1, color='black', alpha=0.7, label='Close')
        
        # 繪製買賣點
        for _, trade in trades_df.iterrows():
            # 判斷顏色和標記
            if trade.get('direction', 'long') == 'long':
                pnl_color = 'green' if trade.get('pnl', 0) >= 0 else 'red'
                entry_marker = '^'  # 買入
                exit_marker = 'v'   # 賣出
            else:
                pnl_color = 'red' if trade.get('pnl', 0) >= 0 else 'green'
                entry_marker = 'v'  # 賣出
                exit_marker = '^'   # 買入（空單）
            
            # 進場點
            if 'entry_time' in trade and pd.notna(trade['entry_time']):
                ax1.scatter(trade['entry_time'], trade['entry_price'],
                           marker=entry_marker, s=150, color=pnl_color, 
                           edgecolor='black', linewidth=0.5, zorder=10)
            
            # 出場點
            if 'exit_time' in trade and pd.notna(trade['exit_time']):
                ax1.scatter(trade['exit_time'], trade['exit_price'],
                           marker='o', s=100, color=pnl_color, 
                           edgecolor='black', linewidth=0.5, zorder=10,
                           facecolors='none')  # 空心
        
        ax1.set_title(title, fontsize=14, fontweight='bold')
        ax1.set_ylabel('Price ($)', fontsize=12)
        ax1.legend(loc='upper left', fontsize=9)
        ax1.grid(True, alpha=0.3)
        ax1.set_xlim(df['datetime'].min(), df['datetime'].max())
        
        # 成交量圖
        ax2 = plt.subplot2grid((3, 1), (2, 0), sharex=ax1)
        
        # 根據漲跌顯示顏色
        colors = ['green' if df['close'].iloc[i] >= df['open'].iloc[i] else 'red' 
                  for i in range(len(df))]
        ax2.bar(df['datetime'], df['volume'], color=colors, alpha=0.5, width=0.8)
        
        ax2.set_ylabel('Volume', fontsize=12)
        ax2.set_xlabel('Date', fontsize=12)
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if filename is None:
            filename = f"trades_indicators_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.png"
        
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()
        
        return str(filepath)
    
    def plot_optimization_heatmap(
        self,
        results_df: pd.DataFrame,
        param_x: str,
        param_y: str,
        metric: str = "sharpe_ratio",
        title: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> Optional[str]:
        """
        繪製參數優化熱力圖
        
        Args:
            results_df: 網格掃描結果
            param_x: X 軸參數名稱
            param_y: Y 軸參數名稱
            metric: 要顯示的指標
            title: 圖表標題
            filename: 輸出檔名
            
        Returns:
            輸出檔案路徑
        """
        if not MATPLOTLIB_AVAILABLE:
            return None
        
        if param_x not in results_df.columns or param_y not in results_df.columns:
            print(f"⚠️ 參數 {param_x} 或 {param_y} 不存在")
            return None
        
        # 建立透視表
        pivot = results_df.pivot_table(
            values=metric,
            index=param_y,
            columns=param_x,
            aggfunc='mean'
        )
        
        fig, ax = plt.subplots(figsize=(10, 8))
        
        sns.heatmap(pivot, annot=True, fmt='.2f', cmap='RdYlGn', 
                   center=0, ax=ax, cbar_kws={'label': metric})
        
        if title is None:
            title = f"Optimization Heatmap: {metric}"
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel(param_x, fontsize=12)
        ax.set_ylabel(param_y, fontsize=12)
        
        plt.tight_layout()
        
        if filename is None:
            filename = f"heatmap_{metric}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.png"
        
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()
        
        return str(filepath)
    
    def plot_walk_forward_results(
        self,
        folds_df: pd.DataFrame,
        equity_df: pd.DataFrame,
        title: str = "Walk-Forward Results",
        filename: Optional[str] = None,
    ) -> Optional[str]:
        """
        繪製 Walk-Forward 結果
        
        Args:
            folds_df: fold 結果
            equity_df: 合併後的 equity curve
            title: 圖表標題
            filename: 輸出檔名
            
        Returns:
            輸出檔案路徑
        """
        if not MATPLOTLIB_AVAILABLE:
            return None
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        # 1. Equity Curve
        ax1 = axes[0, 0]
        ax1.plot(equity_df['datetime'], equity_df['equity'], linewidth=1.5)
        ax1.set_title('Equity Curve', fontsize=12, fontweight='bold')
        ax1.set_xlabel('Date')
        ax1.set_ylabel('Equity')
        ax1.grid(True, alpha=0.3)
        
        # 2. Test Returns by Fold
        ax2 = axes[0, 1]
        if 'test_total_return' in folds_df.columns:
            colors = ['green' if x >= 0 else 'red' for x in folds_df['test_total_return']]
            ax2.bar(range(len(folds_df)), folds_df['test_total_return'] * 100, color=colors)
            ax2.set_title('Test Returns by Fold', fontsize=12, fontweight='bold')
            ax2.set_xlabel('Fold')
            ax2.set_ylabel('Return (%)')
            ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            ax2.grid(True, alpha=0.3)
        
        # 3. Sharpe by Fold
        ax3 = axes[1, 0]
        if 'test_sharpe_ratio' in folds_df.columns:
            colors = ['green' if x >= 0 else 'red' for x in folds_df['test_sharpe_ratio']]
            ax3.bar(range(len(folds_df)), folds_df['test_sharpe_ratio'], color=colors)
            ax3.set_title('Sharpe Ratio by Fold', fontsize=12, fontweight='bold')
            ax3.set_xlabel('Fold')
            ax3.set_ylabel('Sharpe')
            ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            ax3.grid(True, alpha=0.3)
        
        # 4. Best Parameters Distribution (if applicable)
        ax4 = axes[1, 1]
        param_cols = [c for c in folds_df.columns if 'window' in c.lower()]
        if param_cols:
            for col in param_cols:
                ax4.scatter(range(len(folds_df)), folds_df[col], label=col, s=50)
            ax4.set_title('Best Parameters by Fold', fontsize=12, fontweight='bold')
            ax4.set_xlabel('Fold')
            ax4.set_ylabel('Parameter Value')
            ax4.legend()
            ax4.grid(True, alpha=0.3)
        
        if title:
            fig.suptitle(title, fontsize=14, fontweight='bold')
        
        plt.tight_layout()
        
        if filename is None:
            filename = f"walkforward_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.png"
        
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()
        
        return str(filepath)
    
    def generate_html_report(
        self,
        title: str,
        metrics: Dict[str, Any],
        charts: List[str] = None,
        output_filename: Optional[str] = None,
    ) -> str:
        """
        生成 HTML 報告
        
        Args:
            title: 報告標題
            metrics: 指標字典
            charts: 圖表檔案路徑列表
            output_filename: 輸出檔名
            
        Returns:
            輸出檔案路徑
        """
        if output_filename is None:
            output_filename = f"report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.html"
        
        filepath = self.output_dir / output_filename
        
        # 構建 HTML
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
        }}
        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .metric-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .metric-label {{
            color: #666;
            font-size: 14px;
            margin-bottom: 5px;
        }}
        .metric-value {{
            font-size: 24px;
            font-weight: bold;
            color: #333;
        }}
        .metric-value.positive {{ color: #28a745; }}
        .metric-value.negative {{ color: #dc3545; }}
        .charts {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        .chart {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .chart img {{
            max-width: 100%;
            height: auto;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            color: #666;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{title}</h1>
        <p>Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <h2>📊 Performance Metrics</h2>
    <div class="metrics">
"""
        
        # 添加指標
        for key, value in metrics.items():
            if isinstance(value, float):
                if 'return' in key.lower() or 'drawdown' in key.lower():
                    display_value = f"{value*100:.2f}%"
                    css_class = "positive" if value >= 0 else "negative" if 'drawdown' not in key.lower() else "negative"
                elif 'sharpe' in key.lower() or 'sortino' in key.lower() or 'calmar' in key.lower():
                    display_value = f"{value:.2f}"
                    css_class = "positive" if value >= 0 else "negative"
                elif 'win' in key.lower():
                    display_value = f"{value*100:.2f}%"
                    css_class = "positive" if value >= 0.5 else "negative"
                else:
                    display_value = f"{value:.2f}"
                    css_class = ""
            else:
                display_value = str(value)
                css_class = ""
            
            html += f"""
        <div class="metric-card">
            <div class="metric-label">{key.replace('_', ' ').title()}</div>
            <div class="metric-value {css_class}">{display_value}</div>
        </div>
"""
        
        html += """
    </div>
"""
        
        # 添加圖表
        if charts:
            html += """
    <h2>📈 Charts</h2>
    <div class="charts">
"""
            for chart_path in charts:
                if chart_path and os.path.exists(chart_path):
                    filename = os.path.basename(chart_path)
                    html += f"""
        <div class="chart">
            <img src="{filename}" alt="{filename}">
        </div>
"""
            html += """
    </div>
"""
        
        html += """
    <div class="footer">
        <p>Crypto Backtester - Generated Report</p>
    </div>
</body>
</html>
"""
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
        
        return str(filepath)


def generate_optimization_report(
    results_df: pd.DataFrame,
    output_dir: str = "reports",
    title: str = "Optimization Results",
) -> Dict[str, str]:
    """
    生成完整的優化報告
    
    Args:
        results_df: 優化結果
        output_dir: 輸出目錄
        title: 報告標題
        
    Returns:
        生成的檔案路徑字典
    """
    generator = ReportGenerator(output_dir)
    
    output_files = {}
    
    # 找出參數欄位
    metric_cols = ['total_return', 'annualized_return', 'max_drawdown',
                   'sharpe_ratio', 'sortino_ratio', 'calmar_ratio',
                   'total_trades', 'win_rate', 'profit_factor']
    
    param_cols = [c for c in results_df.columns 
                  if c not in metric_cols + ['error', 'state', 'trial_number', 'value']]
    
    # 標準化欄位名稱
    df = results_df.copy()
    if 'value' in df.columns and 'sharpe_ratio' not in df.columns:
        df['sharpe_ratio'] = df['value']
    
    # 繪製熱力圖（如果參數是數值）
    if len(param_cols) >= 2:
        numeric_params = [c for c in param_cols 
                        if df[c].dtype in ['int64', 'float64']]
        if len(numeric_params) >= 2:
            for metric in ['sharpe_ratio', 'total_return']:
                if metric in df.columns:
                    path = generator.plot_optimization_heatmap(
                        df.dropna(subset=[metric]),
                        numeric_params[0],
                        numeric_params[1],
                        metric=metric,
                    )
                    if path:
                        output_files[f"heatmap_{metric}"] = path
    
    # 生成 HTML 報告
    # 獲取 top 結果的指標
    metrics = {}
    for col in ['sharpe_ratio', 'total_return', 'max_drawdown', 'win_rate']:
        if col in df.columns:
            top_val = df.dropna(subset=[col])[col].max()
            metrics[col] = top_val
    
    # 添加最佳參數
    for col in param_cols:
        if col in df.columns:
            best_val = df.dropna(subset=['sharpe_ratio'] if 'sharpe_ratio' in df.columns else ['value']).iloc[0][col]
            metrics[f"best_{col}"] = best_val
    
    html_path = generator.generate_html_report(
        title=title,
        metrics=metrics,
        charts=list(output_files.values()),
    )
    output_files["html_report"] = html_path
    
    return output_files
