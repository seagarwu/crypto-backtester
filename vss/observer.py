"""
市場觀察器

即時監控市場數據流，每次新 K 棒產生時觸發 VSS 分析。
"""

import pandas as pd
import time
from datetime import datetime, timedelta
from typing import Callable, Optional, Dict, Any
from threading import Thread, Event
import logging

from .types import VSSAnalysisResult
from .analyzer import VSSAnalyzer

logger = logging.getLogger(__name__)


class MarketObserver:
    """
    市場觀察器
    
    持續監控市場數據，並在每次新數據到來時觸發分析。
    支援即時數據流與歷史數據回放。
    """
    
    def __init__(
        self,
        analyzer: Optional[VSSAnalyzer] = None,
        callback: Optional[Callable[[VSSAnalysisResult], None]] = None,
        symbols: list[str] = None,
        intervals: list[str] = None,
    ):
        """
        初始化觀察器
        
        Args:
            analyzer: VSS 分析引擎實例
            callback: 分析結果回調函數
            symbols: 監控的標的列表
            intervals: 監控的時間週期列表
        """
        self.analyzer = analyzer or VSSAnalyzer()
        self.callback = callback
        self.symbols = symbols or ["BTCUSDT"]
        self.intervals = intervals or ["1h"]
        
        # 內部狀態
        self._running = Event()
        self._data_cache: Dict[str, pd.DataFrame] = {}
        self._analysis_history: Dict[str, list[VSSAnalysisResult]] = {}
        
        # 數據獲取鉤子（可自定義）
        self._data_fetcher: Optional[Callable] = None
    
    def set_data_fetcher(self, fetcher: Callable[[str, str, Optional[int], Optional[int]], pd.DataFrame]):
        """
        設置數據獲取函數
        
        Args:
            fetcher: 函數簽名為 (symbol, interval, start_time, end_time) -> pd.DataFrame
        """
        self._data_fetcher = fetcher
    
    def start_monitoring(
        self,
        lookback_bars: int = 200,
        poll_interval: int = 60,
    ):
        """
        開始監控市場
        
        Args:
            lookback_bars: 每次獲取的歷史 K 棒數量
            poll_interval: 輪詢間隔（秒）
        """
        if self._running.is_set():
            logger.warning("Observer is already running")
            return
        
        self._running.set()
        self._monitor_thread = Thread(
            target=self._monitor_loop,
            args=(lookback_bars, poll_interval),
            daemon=True,
        )
        self._monitor_thread.start()
        logger.info(f"Started monitoring: {self.symbols} on {self.intervals}")
    
    def stop_monitoring(self):
        """停止監控"""
        if not self._running.is_set():
            return
        
        self._running.clear()
        if hasattr(self, '_monitor_thread'):
            self._monitor_thread.join(timeout=5)
        logger.info("Stopped monitoring")
    
    def _monitor_loop(self, lookback_bars: int, poll_interval: int):
        """監控主循環"""
        last_timestamps: Dict[str, datetime] = {}
        
        while self._running.is_set():
            try:
                for symbol in self.symbols:
                    for interval in self.intervals:
                        key = f"{symbol}_{interval}"
                        
                        # 獲取最新數據
                        df = self._fetch_data(symbol, interval, lookback_bars)
                        
                        if df is None or len(df) == 0:
                            continue
                        
                        # 檢查是否有新數據
                        latest_time = df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
                        last_time = last_timestamps.get(key)
                        
                        if last_time is None or latest_time > last_time:
                            # 有新數據，執行分析
                            result = self.analyzer.analyze(
                                df=df,
                                symbol=symbol,
                                interval=interval,
                            )
                            
                            # 記錄歷史
                            if key not in self._analysis_history:
                                self._analysis_history[key] = []
                            self._analysis_history[key].append(result)
                            
                            # 觸發回調
                            if self.callback:
                                self.callback(result)
                            
                            last_timestamps[key] = latest_time
                            logger.info(f"Analyzed {symbol} {interval}: {result.market_state.description}")
                
                # 等待下一輪
                time.sleep(poll_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(poll_interval)
    
    def _fetch_data(
        self,
        symbol: str,
        interval: str,
        lookback_bars: int
    ) -> Optional[pd.DataFrame]:
        """獲取市場數據"""
        if self._data_fetcher:
            return self._data_fetcher(symbol, interval, None, None)
        
        # 嘗試從 cache 獲取（如果需要回測模式）
        key = f"{symbol}_{interval}"
        if key in self._data_cache:
            return self._data_cache[key]
        
        return None
    
    def load_historical_data(
        self,
        symbol: str,
        interval: str,
        df: pd.DataFrame,
    ):
        """
        載入歷史數據用於分析
        
        Args:
            symbol: 標的
            interval: 時間週期
            df: K 線數據 DataFrame
        """
        key = f"{symbol}_{interval}"
        self._data_cache[key] = df
    
    def analyze_current(
        self,
        symbol: str,
        interval: str,
    ) -> Optional[VSSAnalysisResult]:
        """
        分析當前市場狀態
        
        Args:
            symbol: 標的
            interval: 時間週期
            
        Returns:
            VSSAnalysisResult or None
        """
        key = f"{symbol}_{interval}"
        df = self._data_cache.get(key)
        
        if df is None:
            logger.warning(f"No data available for {key}")
            return None
        
        return self.analyzer.analyze(df=df, symbol=symbol, interval=interval)
    
    def get_analysis_history(
        self,
        symbol: str,
        interval: str,
    ) -> list[VSSAnalysisResult]:
        """
        獲取分析歷史
        
        Args:
            symbol: 標的
            interval: 時間週期
            
        Returns:
            分析結果列表
        """
        key = f"{symbol}_{interval}"
        return self._analysis_history.get(key, [])
    
    def is_running(self) -> bool:
        """檢查是否正在監控"""
        return self._running.is_set()


class BacktestObserver(MarketObserver):
    """
    回測觀察器
    
    用於歷史數據回放的觀察器，
    模擬即時市場分析。
    """
    
    def __init__(
        self,
        analyzer: Optional[VSSAnalyzer] = None,
        callback: Optional[Callable[[VSSAnalysisResult], None]] = None,
    ):
        super().__init__(analyzer, callback)
        self._current_index: Dict[str, int] = {}
    
    def run_backtest(
        self,
        df: pd.DataFrame,
        symbol: str = "UNKNOWN",
        interval: str = "1h",
        start_bar: int = 50,
    ):
        """
        運行回放模式
        
        Args:
            df: 歷史 K 線數據
            symbol: 標的
            interval: 時間週期
            start_bar: 起始 K 棒索引（需要足夠歷史數據計算指標）
        """
        key = f"{symbol}_{interval}"
        self._current_index[key] = start_bar
        
        for i in range(start_bar, len(df)):
            # 獲取到當前為止的數據
            data = df.iloc[:i+1]
            
            # 分析
            result = self.analyzer.analyze(
                df=data,
                symbol=symbol,
                interval=interval,
            )
            
            # 記錄歷史
            if key not in self._analysis_history:
                self._analysis_history[key] = []
            self._analysis_history[key].append(result)
            
            # 觸發回調
            if self.callback:
                self.callback(result)
            
            # 更新索引
            self._current_index[key] = i
            
            # 可選：記錄進度
            if (i - start_bar) % 100 == 0:
                logger.info(f"Progress: {i - start_bar}/{len(df) - start_bar}")
    
    def get_current_state(
        self,
        symbol: str,
        interval: str,
    ) -> Optional[MarketObserver]:
        """獲取當前市場狀態"""
        key = f"{symbol}_{interval}"
        history = self._analysis_history.get(key, [])
        
        if len(history) == 0:
            return None
        
        return history[-1]
