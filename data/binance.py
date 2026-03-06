"""
Binance 歷史 K 線資料下載模組

提供從 Binance 公開 API 下載歷史 K 線資料的功能。
"""

import os
from datetime import datetime
from typing import Optional

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# Binance API 端點
BINANCE_KLINE_URL = "https://api.binance.com/api/v3/klines"

# 預設欄位名稱（從 Binance API 回傳）
BINANCE_COLUMNS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "trade_count",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
    "ignore",
]

# 我們需要的核心欄位
REQUIRED_COLUMNS = ["datetime", "open", "high", "low", "close", "volume"]

# 支援的 K 線間隔
VALID_INTERVALS = [
    "1s", "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "6h", "8h", "12h",
    "1d", "3d", "1w", "1M",
]

# K 線間隔對應的毫秒數
INTERVAL_TO_MS = {
    "1s": 1_000,
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "6h": 21_600_000,
    "8h": 28_800_000,
    "12h": 43_200_000,
    "1d": 86_400_000,
    "3d": 259_200_000,
    "1w": 604_800_000,
    "1M": 2_592_000_000,  # 30天
}


class BinanceAPIError(Exception):
    """Binance API 相關錯誤"""
    pass


class UnsupportedIntervalError(Exception):
    """不支援的 K 線間隔"""
    pass


class DataDownloader:
    """Binance K 線資料下載器"""

    def __init__(self, timeout: int = 30):
        """
        初始化下載器

        Args:
            timeout: API 請求超時秒數
        """
        self.timeout = timeout
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """建立帶有重試機制的 HTTP Session"""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def validate_interval(self, interval: str) -> bool:
        """驗證 K 線間隔是否有效"""
        return interval in VALID_INTERVALS

    def download_klines(
        self,
        symbol: str,
        interval: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        """
        下載 K 線資料

        Args:
            symbol: 交易對，如 'BTCUSDT'
            interval: K 線間隔，如 '1h', '4h', '1d'
            start_time: 開始時間（Unix timestamp in ms），若為 None 則不限制
            end_time: 結束時間（Unix timestamp in ms），若為 None 則不限制
            limit: 每次 API 請求的最大筆數（最大值 1000）

        Returns:
            包含 K 線資料的 DataFrame

        Raises:
            BinanceAPIError: API 請求失敗時
            ValueError: 參數驗證失敗時
        """
        # 驗證參數
        if not symbol:
            raise ValueError("symbol 不能為空")
        symbol = symbol.upper()

        if not self.validate_interval(interval):
            raise ValueError(f"無效的 interval: {interval}。支援: {VALID_INTERVALS}")

        if limit < 1 or limit > 1000:
            raise ValueError("limit 必須在 1-1000 之間")

        # 建構請求參數
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        }

        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time

        # 發送請求
        try:
            response = self.session.get(
                BINANCE_KLINE_URL,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise BinanceAPIError(f"API 請求失敗: {e}") from e

        # 解析回應
        data = response.json()

        if not data:
            return pd.DataFrame(columns=REQUIRED_COLUMNS)

        # 轉換為 DataFrame
        df = pd.DataFrame(data, columns=BINANCE_COLUMNS)

        # 選擇我們需要的欄位並轉型
        df = df[["open_time", "open", "high", "low", "close", "volume"]].copy()

        # 轉換時間（從毫秒轉為 datetime）
        df["datetime"] = pd.to_datetime(df["open_time"], unit="ms")

        # 數值欄位轉型
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # 移除不需要的欄位
        df = df.drop(columns=["open_time"])

        # 依時間排序
        df = df.sort_values("datetime").reset_index(drop=True)

        # 檢查並移除重複資料
        df = self._remove_duplicates(df)

        return df

    def _remove_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """移除重複的時間戳"""
        if df.empty:
            return df

        initial_len = len(df)
        df = df.drop_duplicates(subset=["datetime"], keep="first")

        if len(df) < initial_len:
            print(f"警告: 移除了 {initial_len - len(df)} 條重複記錄")

        return df.reset_index(drop=True)

    def download_to_csv(
        self,
        symbol: str,
        interval: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 1000,
        output_path: Optional[str] = None,
    ) -> str:
        """
        下載 K 線資料並存為 CSV

        Args:
            symbol: 交易對
            interval: K 線間隔
            start_time: 開始時間（Unix timestamp in ms）
            end_time: 結束時間（Unix timestamp in ms）
            limit: 每次請求的最大筆數
            output_path: 輸出檔案路徑，若為 None 則自動產生

        Returns:
            輸出檔案的路徑
        """
        df = self.download_klines(
            symbol=symbol,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

        if df.empty:
            print(f"警告: 沒有下載到任何資料 ({symbol} {interval})")
            return ""

        # 自動產生輸出路徑
        if output_path is None:
            os.makedirs("data", exist_ok=True)
            output_path = f"data/{symbol}_{interval}_{len(df)}.csv"

        # 存檔
        df.to_csv(output_path, index=False)
        print(f"已儲存 {len(df)} 筆資料至: {output_path}")

        return output_path

    def download_klines_range(
        self,
        symbol: str,
        interval: str,
        start_time: int,
        end_time: int,
        output_path: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        下載指定時間範圍內的 K 線資料（自動分頁）

        會自動循環呼叫 API 直到抓滿範圍或沒有更多資料。

        Args:
            symbol: 交易對，如 'BTCUSDT'
            interval: K 線間隔，如 '1h', '4h', '1d'
            start_time: 開始時間（Unix timestamp in ms）
            end_time: 結束時間（Unix timestamp in ms）
            output_path: 輸出 CSV 檔案路徑，若提供則存檔

        Returns:
            包含 K 線資料的 DataFrame
        """
        # 驗證 interval 並取得毫秒數
        interval_ms = parse_interval_to_ms(interval)

        all_data = []
        current_start = start_time

        print(f"開始下載 {symbol} {interval} 從 {timestamp_to_datetime(start_time)} ...")

        while current_start < end_time:
            # 計算這次請求的 end_time
            # 注意：Binance 的 endTime 是 inclusive，但我們用下一個區間的開始
            request_end = min(current_start + interval_ms * 1000, end_time)

            try:
                df = self.download_klines(
                    symbol=symbol,
                    interval=interval,
                    start_time=current_start,
                    end_time=request_end,
                    limit=1000,
                )
            except BinanceAPIError as e:
                print(f"下載失敗: {e}")
                break

            if df.empty:
                # 沒有更多資料
                break

            all_data.append(df)
            print(f"  已下載 {len(df)} 筆 (進度: {len(all_data)} 頁)")

            # 取得最後一筆的 open_time，作為下一頁的 startTime
            # 避免重疊，用最後一筆的 close_time + 1ms
            last_open_time = int(pd.Timestamp(df["datetime"].iloc[-1]).timestamp() * 1000)
            current_start = last_open_time + interval_ms

            # 防呆：如果卡住就退出
            if len(all_data) > 10000:
                print("警告: 達到最大頁數限制 (10000)")
                break

        if not all_data:
            print(f"警告: 沒有下載到任何資料 ({symbol} {interval})")
            return pd.DataFrame(columns=REQUIRED_COLUMNS)

        # 合併所有資料
        combined = pd.concat(all_data, ignore_index=True)

        # 去重
        combined = combined.drop_duplicates(subset=["datetime"], keep="first")

        # 排序
        combined = combined.sort_values("datetime").reset_index(drop=True)

        # 只保留時間範圍內的資料
        start_dt = pd.to_datetime(start_time, unit="ms")
        end_dt = pd.to_datetime(end_time, unit="ms")
        combined = combined[
            (combined["datetime"] >= start_dt) &
            (combined["datetime"] <= end_dt)
        ].reset_index(drop=True)

        print(f"下載完成: 總共 {len(combined)} 筆資料")

        # 存檔
        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            combined.to_csv(output_path, index=False)
            print(f"已儲存至: {output_path}")

        return combined


# ============================================================================
# 便捷函數
# ============================================================================

def parse_interval_to_ms(interval: str) -> int:
    """
    將 K 線間隔轉換為毫秒數

    Args:
        interval: K 線間隔，如 '1m', '1h', '1d', '1w'

    Returns:
        對應的毫秒數

    Raises:
        UnsupportedIntervalError: 不支援的間隔
    """
    # 先檢查是否有效（避免 1M 被當成 1m）
    if interval not in VALID_INTERVALS:
        raise UnsupportedIntervalError(
            f"不支援的間隔: {interval}。支援: {VALID_INTERVALS}"
        )
    
    return INTERVAL_TO_MS[interval]


def download_binance_data(
    symbol: str,
    interval: str,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    output_path: Optional[str] = None,
) -> pd.DataFrame:
    """
    便捷函數：下載 Binance K 線資料（單次最多 1000 筆）

    若需要下載大量資料，請使用 download_klines_range()。

    Args:
        symbol: 交易對，如 'BTCUSDT'
        interval: K 線間隔，如 '1h', '4h', '1d'
        start_time: 開始時間（Unix timestamp in ms）
        end_time: 結束時間（Unix timestamp in ms）
        output_path: 輸出 CSV 檔案路徑，若提供則存檔

    Returns:
        包含 K 線資料的 DataFrame
    """
    downloader = DataDownloader()

    # 若需要存檔
    if output_path:
        return downloader.download_to_csv(
            symbol=symbol,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
            output_path=output_path,
        )

    # 否則只回傳 DataFrame
    return downloader.download_klines(
        symbol=symbol,
        interval=interval,
        start_time=start_time,
        end_time=end_time,
    )


def download_klines_range(
    symbol: str,
    interval: str,
    start_time: int,
    end_time: int,
    output_path: Optional[str] = None,
) -> pd.DataFrame:
    """
    便捷函數：下載指定時間範圍內的 K 線資料（自動分頁）

    會自動循環呼叫 API 直到抓滿範圍或沒有更多資料。
    適合下載超過 1000 筆的歷史資料。

    Args:
        symbol: 交易對，如 'BTCUSDT'
        interval: K 線間隔，如 '1h', '4h', '1d'
        start_time: 開始時間（Unix timestamp in ms）
        end_time: 結束時間（Unix timestamp in ms）
        output_path: 輸出 CSV 檔案路徑，若提供則存檔

    Returns:
        包含 K 線資料的 DataFrame
    """
    downloader = DataDownloader()
    return downloader.download_klines_range(
        symbol=symbol,
        interval=interval,
        start_time=start_time,
        end_time=end_time,
        output_path=output_path,
    )


def datetime_to_timestamp(dt: datetime) -> int:
    """將 datetime 轉換為 Unix timestamp（毫秒）"""
    # 如果沒有時區資訊，假设为 UTC
    if dt.tzinfo is None:
        from datetime import timezone
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def timestamp_to_datetime(ts: int) -> datetime:
    """將 Unix timestamp（毫秒）轉換為 datetime"""
    # 返回 UTC 時區的 datetime
    from datetime import timezone
    return datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
