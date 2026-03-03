"""
資料模組

提供 Binance 資料下載與 CSV 載入功能。
"""

from .binance import (
    BinanceAPIError,
    UnsupportedIntervalError,
    DataDownloader,
    download_binance_data,
    download_klines_range,
    parse_interval_to_ms,
    datetime_to_timestamp,
    timestamp_to_datetime,
)
from .loader import (
    DataLoadError,
    DataLoader,
    load_csv,
    load_multiple_csv,
)

__all__ = [
    # Binance
    "BinanceAPIError",
    "UnsupportedIntervalError",
    "DataDownloader",
    "download_binance_data",
    "download_klines_range",
    "parse_interval_to_ms",
    "datetime_to_timestamp",
    "timestamp_to_datetime",
    # Loader
    "DataLoadError",
    "DataLoader",
    "load_csv",
    "load_multiple_csv",
]
