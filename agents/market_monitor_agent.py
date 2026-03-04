"""
Market Monitor Agent - 市場資料監控 Agent

職責：
1. 定時抓取 Binance 最新 K 線資料
2. 存到本地資料庫（CSV）
3. 偵測市場異常（劇烈波動、異常交易量）
4. 通知其他 Agents 有新資料
"""

import os
import time
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable
from pathlib import Path

import pandas as pd

from data.binance import (
    download_klines_range,
    download_binance_data,
    datetime_to_timestamp,
    parse_interval_to_ms,
)


class MarketDataManager:
    """市場資料管理器"""
    
    def __init__(self, data_dir: str = "data/market"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def get_latest_file(self, symbol: str, interval: str) -> Path:
        """取得最新資料檔案路徑"""
        return self.data_dir / f"{symbol}_{interval}_latest.csv"
    
    def load_latest(self, symbol: str, interval: str) -> Optional[pd.DataFrame]:
        """載入最新資料"""
        filepath = self.get_latest_file(symbol, interval)
        if filepath.exists():
            return pd.read_csv(filepath, parse_dates=["datetime"])
        return None
    
    def save_latest(self, df: pd.DataFrame, symbol: str, interval: str) -> None:
        """儲存最新資料"""
        filepath = self.get_latest_file(symbol, interval)
        df.to_csv(filepath, index=False)
    
    def append_data(self, df: pd.DataFrame, symbol: str, interval: str) -> None:
        """追加新資料到現有資料"""
        existing = self.load_latest(symbol, interval)
        
        if existing is None:
            self.save_latest(df, symbol, interval)
            return
        
        # 合併並去重
        combined = pd.concat([existing, df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["datetime"], keep="last")
        combined = combined.sort_values("datetime").reset_index(drop=True)
        
        self.save_latest(combined, symbol, interval)


class MarketMonitorAgent:
    """
    Market Monitor Agent
    
    負責定時抓取並更新市場資料。
    """
    
    def __init__(
        self,
        symbols: List[str] = None,
        intervals: List[str] = None,
        data_dir: str = "data/market",
        fetch_interval_minutes: int = 60,
        lookback_days: int = 7,
    ):
        """
        初始化 Market Monitor Agent
        
        Args:
            symbols: 監控的交易對列表
            intervals: K 線間隔列表
            data_dir: 資料儲存目錄
            fetch_interval_minutes: 抓取間隔（分鐘）
            lookback_days: 每次抓回的歷史天數
        """
        self.symbols = symbols or ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        self.intervals = intervals or ["1h", "4h", "1d"]
        self.data_manager = MarketDataManager(data_dir)
        self.fetch_interval = fetch_interval_minutes * 60  # 轉為秒
        self.lookback_days = lookback_days
        
        # 回调函数 - 用于通知其他 Agents
        self.callbacks: List[Callable[[str, pd.DataFrame], None]] = []
        
        # 運行狀態
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # 市場狀態
        self.last_fetch_time: Optional[datetime] = None
        self.fetch_history: List[Dict[str, Any]] = []
    
    def register_callback(self, callback: Callable[[str, pd.DataFrame], None]) -> None:
        """註冊回調函數 - 有新資料時通知"""
        self.callbacks.append(callback)
    
    def start(self) -> None:
        """啟動 Agent"""
        if self._running:
            print("⚠️ Agent 已在運行中")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        print(f"🚀 Market Monitor Agent 已啟動")
        print(f"   監控: {self.symbols}")
        print(f"   間隔: {self.fetch_interval // 60} 分鐘")
    
    def stop(self) -> None:
        """停止 Agent"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("🛑 Market Monitor Agent 已停止")
    
    def fetch_once(self) -> Dict[str, Dict[str, pd.DataFrame]]:
        """
        手動觸發一次資料抓取
        
        Returns:
            {symbol: {interval: DataFrame}}
        """
        results = {}
        
        for symbol in self.symbols:
            results[symbol] = {}
            
            for interval in self.intervals:
                print(f"📥 抓取 {symbol} {interval}...")
                
                try:
                    # 計算時間範圍
                    end_time = datetime_to_timestamp(datetime.now())
                    start_time = datetime_to_timestamp(
                        datetime.now() - timedelta(days=self.lookback_days)
                    )
                    
                    # 抓取資料
                    df = download_klines_range(
                        symbol=symbol,
                        interval=interval,
                        start_time=start_time,
                        end_time=end_time,
                    )
                    
                    if not df.empty:
                        # 儲存
                        self.data_manager.append_data(df, symbol, interval)
                        results[symbol][interval] = df
                        
                        # 記錄
                        self.last_fetch_time = datetime.now()
                        self.fetch_history.append({
                            "time": self.last_fetch_time,
                            "symbol": symbol,
                            "interval": interval,
                            "rows": len(df),
                        })
                        
                        # 通知回調
                        for callback in self.callbacks:
                            try:
                                callback(symbol, df)
                            except Exception as e:
                                print(f"⚠️ 回調錯誤: {e}")
                        
                        print(f"   ✅ 取得 {len(df)} 筆資料")
                    else:
                        print(f"   ⚠️ 無資料")
                        
                except Exception as e:
                    print(f"   ❌ 錯誤: {e}")
        
        return results
    
    def get_latest_data(self, symbol: str, interval: str) -> Optional[pd.DataFrame]:
        """取得指定交易對的最新資料"""
        return self.data_manager.load_latest(symbol, interval)
    
    def get_market_summary(self) -> Dict[str, Any]:
        """取得市場監控摘要"""
        summary = {
            "running": self._running,
            "last_fetch": self.last_fetch_time.isoformat() if self.last_fetch_time else None,
            "symbols": {},
        }
        
        for symbol in self.symbols:
            latest_data = {}
            for interval in self.intervals:
                df = self.get_latest_data(symbol, interval)
                if df is not None and not df.empty:
                    latest_data[interval] = {
                        "rows": len(df),
                        "start": str(df["datetime"].min()),
                        "end": str(df["datetime"].max()),
                        "latest_close": float(df["close"].iloc[-1]),
                    }
            summary["symbols"][symbol] = latest_data
        
        return summary
    
    def _run_loop(self) -> None:
        """執行循環"""
        # 初始抓取
        self.fetch_once()
        
        # 循環
        while self._running:
            time.sleep(self.fetch_interval)
            if self._running:
                self.fetch_once()


# ==================== 便捷函數 ====================

def create_market_monitor(
    symbols: List[str] = None,
    intervals: List[str] = None,
    data_dir: str = "data/market",
) -> MarketMonitorAgent:
    """建立 Market Monitor Agent"""
    return MarketMonitorAgent(
        symbols=symbols,
        intervals=intervals,
        data_dir=data_dir,
    )
