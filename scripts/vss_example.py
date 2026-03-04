"""
VSS 交易系統使用範例

展示如何使用 VSS 分析與人機對齊系統。
"""

import pandas as pd
import numpy as np
from datetime import datetime

from vss.types import HumanJudgment, TrendDirection, PatternType
from vss.analyzer import VSSAnalyzer
from alignment.controller import DecisionController


def generate_sample_data(n_bars: int = 100, seed: int = 42) -> pd.DataFrame:
    """生成模擬 K 線數據"""
    np.random.seed(seed)
    
    dates = pd.date_range(start='2024-01-01', periods=n_bars, freq='1h')
    
    # 模擬價格走勢
    returns = np.random.randn(n_bars) * 0.02
    prices = 50000 * np.exp(np.cumsum(returns))
    
    # 生成 OHLCV
    df = pd.DataFrame({
        'open': prices * (1 + np.random.randn(n_bars) * 0.005),
        'high': prices * (1 + np.abs(np.random.randn(n_bars) * 0.01)),
        'low': prices * (1 - np.abs(np.random.randn(n_bars) * 0.01)),
        'close': prices,
        'volume': np.random.randint(1000, 10000, n_bars),
    }, index=dates)
    
    # 確保 high >= open, close 和 low <= open, close
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)
    
    return df


def main():
    print("=" * 60)
    print("VSS 交易系統範例")
    print("=" * 60)
    
    # 1. 生成模擬數據
    print("\n[1] 生成模擬市場數據...")
    df = generate_sample_data(200)
    print(f"    數據範圍: {df.index[0]} ~ {df.index[-1]}")
    print(f"    最新價格: ${df['close'].iloc[-1]:.2f}")
    
    # 2. VSS 分析
    print("\n[2] VSS 市場分析...")
    analyzer = VSSAnalyzer()
    result = analyzer.analyze(df, symbol="BTCUSDT", interval="1h")
    
    print(f"    市場狀態: {result.market_state.description}")
    print(f"    趨勢: {result.market_state.trend.value}")
    print(f"    趨勢信心度: {result.market_state.trend_confidence:.0%}")
    print(f"    動能: {result.market_state.momentum.value}")
    print(f"    波動率: {result.market_state.volatility.value}")
    print(f"    風險等級: {result.risk_level}")
    print(f"    觀察:")
    for obs in result.observations:
        print(f"      - {obs}")
    
    # 3. 人類判斷輸入
    print("\n[3] 輸入人類判斷...")
    human_judgment = HumanJudgment(
        timestamp=datetime.now(),
        symbol="BTCUSDT",
        interval="1h",
        trend=TrendDirection.UP,  # 假設人類判斷會漲
        confidence=0.75,
        notes="看到價格突破下降趨勢線，準備測試前高",
        pattern_observed=None,
    )
    print(f"    人類趨勢判斷: {human_judgment.trend.value}")
    print(f"    信心度: {human_judgment.confidence:.0%}")
    print(f"    備註: {human_judgment.notes}")
    
    # 4. 決策控制器
    print("\n[4] 人機對齊決策...")
    controller = DecisionController(
        alignment_threshold=0.7,
        confidence_threshold=0.6,
    )
    
    decision = controller.process(human_judgment, df)
    
    print(f"    決策: {'批准執行' if decision['decision'] else '拒絕執行'}")
    print(f"    原因: {decision['reason']}")
    print(f"    對齊分數: {decision['alignment_score']:.0%}")
    print(f"    趨勢匹配: {decision['trend_match']}")
    print(f"    差異說明: {decision['difference_notes']}")
    
    if decision.get('suggestion'):
        print(f"    建議:")
        for s in decision['suggestion'].get('suggestions', []):
            print(f"      - {s}")
    
    # 5. 統計資訊
    print("\n[5] 統計資訊...")
    stats = controller.get_statistics()
    if stats:
        print(f"    總決策數: {stats.get('total_decisions', 0)}")
        print(f"    批准數: {stats.get('approved', 0)}")
        print(f"    拒絕數: {stats.get('rejected', 0)}")
        print(f"    批准率: {stats.get('approval_rate', 0):.0%}")
    
    print("\n" + "=" * 60)
    print("範例執行完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
