"""
資料模組

提供 Binance 資料下載與 CSV 載入功能。
"""

from .binance import (
    BinanceAPIError,
    DataDownloader,
    download_binance_data,
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
    "DataDownloader",
    "download_binance_data",
    "datetime_to_timestamp",
    "timestamp_to_datetime",
    # Loader
    "DataLoadError",
    "DataLoader",
    "load_csv",
    "load_multiple_csv",
]
