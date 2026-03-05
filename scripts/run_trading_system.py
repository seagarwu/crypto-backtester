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
        """
    )
    
    parser.add_argument(
        "--mode", 
        choices=["paper", "live"], 
        default="paper",
        help="交易模式 (default: paper)"
    )
    
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["BTCUSDT"],
        help="交易對 (default: BTCUSDT)"
    )
    
    parser.add_argument(
        "--interval",
        default="1h",
        help="K線週期 (default: 1h)"
    )
    
    parser.add_argument(
        "--capital",
        type=float,
        default=10000.0,
        help="初始資金 (default: 10000)"
    )
    
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
    
    args = parser.parse_args()
    
    # 環境檢查
    print("=" * 50)
    print("Multi-Agent Trading System")
    print("=" * 50)
    print(f"模式: {args.mode}")
    print(f"交易對: {args.symbols}")
    print(f"週期: {args.interval}")
    print(f"資金: ${args.capital:,.2f}")
    print("=" * 50)
    
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
        
        # 建立系統
        system = create_trading_system(
            symbols=args.symbols,
            intervals=[args.interval],
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
