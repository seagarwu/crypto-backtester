"""
資料載入模組

載入 CSV 資料並進行基本驗證，提供統一的資料格式給策略與回測引擎使用。
"""

from pathlib import Path
from typing import Optional, List

import pandas as pd


# 必要的欄位
REQUIRED_COLUMNS = ["datetime", "open", "high", "low", "close", "volume"]

# 數值欄位（應該是數字類型）
NUMERIC_COLUMNS = ["open", "high", "low", "close", "volume"]


class DataLoadError(Exception):
    """資料載入相關錯誤"""
    pass


class DataLoader:
    """CSV 資料載入器"""

    def __init__(self, file_path: str):
        """
        初始化資料載入器

        Args:
            file_path: CSV 檔案路徑
        """
        self.file_path = Path(file_path)
        self.df: Optional[pd.DataFrame] = None

    def load(self, parse_dates: bool = True) -> pd.DataFrame:
        """
        載入 CSV 檔案

        Args:
            parse_dates: 是否自動解析日期欄位

        Returns:
            處理後的 DataFrame

        Raises:
            DataLoadError: 載入或驗證失敗時
        """
        if not self.file_path.exists():
            raise DataLoadError(f"檔案不存在: {self.file_path}")

        try:
            df = pd.read_csv(self.file_path)
        except Exception as e:
            raise DataLoadError(f"無法讀取 CSV: {e}") from e

        # 檢查必要欄位
        self._validate_columns(df)

        # 解析日期
        if parse_dates:
            df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")

        # 檢查日期解析
        null_dates = df["datetime"].isna().sum()
        if null_dates > 0:
            raise DataLoadError(f"有 {null_dates} 筆資料的日期無法解析")

        # 數值欄位轉型
        for col in NUMERIC_COLUMNS:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # 檢查缺值
        self._check_missing_values(df)

        # 依日期排序
        df = df.sort_values("datetime").reset_index(drop=True)

        # 檢查重複日期
        self._check_duplicates(df)

        # 檢查價格邏輯
        self._validate_price_logic(df)

        self.df = df
        return df

    def _validate_columns(self, df: pd.DataFrame) -> None:
        """檢查必要欄位"""
        missing_cols = set(REQUIRED_COLUMNS) - set(df.columns)
        if missing_cols:
            raise DataLoadError(
                f"缺少必要欄位: {missing_cols}。需要: {REQUIRED_COLUMNS}"
            )

    def _check_missing_values(self, df: pd.DataFrame) -> None:
        """檢查缺值"""
        missing_info = df[REQUIRED_COLUMNS].isnull().sum()
        missing_cols = missing_info[missing_info > 0]

        if not missing_cols.empty:
            raise DataLoadError(
                f"以下欄位有缺值:\n{missing_cols.to_string()}"
            )

    def _check_duplicates(self, df: pd.DataFrame) -> None:
        """檢查重複的時間戳"""
        duplicates = df["datetime"].duplicated().sum()
        if duplicates > 0:
            raise DataLoadError(f"發現 {duplicates} 筆重複的時間戳")

    def _validate_price_logic(self, df: pd.DataFrame) -> None:
        """驗證價格邏輯（high >= low, high >= open/close 等）"""
        invalid_high = (df["high"] < df["low"]).sum()
        if invalid_high > 0:
            raise DataLoadError(f"發現 {invalid_high} 筆 high < low 的異常資料")

        invalid_ohlc = (
            (df["high"] < df["open"]) |
            (df["high"] < df["close"]) |
            (df["low"] > df["open"]) |
            (df["low"] > df["close"])
        ).sum()

        if invalid_ohlc > 0:
            raise DataLoadError(f"發現 {invalid_ohlc} 筆 OHLC 邏輯異常的資料")

    def get_data(self) -> pd.DataFrame:
        """
        取得載入的資料

        Returns:
            DataFrame
        """
        if self.df is None:
            raise DataLoadError("資料尚未載入，請先呼叫 load()")
        return self.df.copy()

    def get_date_range(self) -> tuple:
        """
        取得資料的日期範圍

        Returns:
            (開始日期, 結束日期) 的 tuple
        """
        if self.df is None:
            raise DataLoadError("資料尚未載入，請先呼叫 load()")
        return (self.df["datetime"].min(), self.df["datetime"].max())


def load_csv(file_path: str) -> pd.DataFrame:
    """
    便捷函數：載入 CSV 檔案

    Args:
        file_path: CSV 檔案路徑

    Returns:
        處理後的 DataFrame
    """
    loader = DataLoader(file_path)
    return loader.load()


def load_multiple_csv(file_paths: List[str]) -> pd.DataFrame:
    """
    載入多個 CSV 檔案並合併

    Args:
        file_paths: CSV 檔案路徑列表

    Returns:
        合併後的 DataFrame
    """
    dfs = []
    for path in file_paths:
        df = load_csv(path)
        dfs.append(df)

    combined = pd.concat(dfs, ignore_index=True)
    combined = combined.drop_duplicates(subset=["datetime"], keep="first")
    combined = combined.sort_values("datetime").reset_index(drop=True)

    return combined
