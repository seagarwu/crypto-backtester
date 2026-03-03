"""
資料載入模組測試
"""

import pytest
import pandas as pd
import os
from datetime import datetime

from data.loader import DataLoader, DataLoadError, load_csv


class TestDataLoader:
    """測試 DataLoader 類別"""

    def test_load_valid_csv(self, tmp_path):
        """測試載入有效的 CSV"""
        # 建立測試 CSV
        csv_file = tmp_path / "test.csv"
        df = pd.DataFrame({
            "datetime": ["2023-01-01 00:00:00", "2023-01-01 01:00:00", "2023-01-01 02:00:00"],
            "open": [100.0, 101.0, 102.0],
            "high": [110.0, 111.0, 112.0],
            "low": [90.0, 91.0, 92.0],
            "close": [105.0, 106.0, 107.0],
            "volume": [1000.0, 1100.0, 1200.0],
        })
        df.to_csv(csv_file, index=False)

        # 載入
        loader = DataLoader(str(csv_file))
        result = loader.load()

        assert len(result) == 3
        assert "datetime" in result.columns
        assert result["close"].iloc[0] == 105.0

    def test_load_missing_columns(self, tmp_path):
        """測試缺少必要欄位"""
        csv_file = tmp_path / "test.csv"
        df = pd.DataFrame({
            "datetime": ["2023-01-01"],
            "close": [100.0],
        })
        df.to_csv(csv_file, index=False)

        loader = DataLoader(str(csv_file))
        with pytest.raises(DataLoadError, match="缺少必要欄位"):
            loader.load()

    def test_load_invalid_date(self, tmp_path):
        """測試無效日期"""
        csv_file = tmp_path / "test.csv"
        df = pd.DataFrame({
            "datetime": ["invalid-date"],
            "open": [100.0],
            "high": [110.0],
            "low": [90.0],
            "close": [105.0],
            "volume": [1000.0],
        })
        df.to_csv(csv_file, index=False)

        loader = DataLoader(str(csv_file))
        with pytest.raises(DataLoadError, match="無法解析"):
            loader.load()

    def test_load_missing_values(self, tmp_path):
        """測試缺值"""
        csv_file = tmp_path / "test.csv"
        df = pd.DataFrame({
            "datetime": ["2023-01-01 00:00:00", "2023-01-01 01:00:00"],
            "open": [100.0, None],
            "high": [110.0, 111.0],
            "low": [90.0, 91.0],
            "close": [105.0, 106.0],
            "volume": [1000.0, 1100.0],
        })
        df.to_csv(csv_file, index=False)

        loader = DataLoader(str(csv_file))
        with pytest.raises(DataLoadError, match="有缺值"):
            loader.load()

    def test_load_price_logic_error(self, tmp_path):
        """測試價格邏輯錯誤"""
        csv_file = tmp_path / "test.csv"
        df = pd.DataFrame({
            "datetime": ["2023-01-01 00:00:00"],
            "open": [100.0],
            "high": [50.0],  # high < low
            "low": [90.0],
            "close": [105.0],
            "volume": [1000.0],
        })
        df.to_csv(csv_file, index=False)

        loader = DataLoader(str(csv_file))
        with pytest.raises(DataLoadError, match="high < low"):
            loader.load()

    def test_load_duplicate_dates(self, tmp_path):
        """測試重複日期"""
        csv_file = tmp_path / "test.csv"
        df = pd.DataFrame({
            "datetime": ["2023-01-01 00:00:00", "2023-01-01 00:00:00"],
            "open": [100.0, 101.0],
            "high": [110.0, 111.0],
            "low": [90.0, 91.0],
            "close": [105.0, 106.0],
            "volume": [1000.0, 1100.0],
        })
        df.to_csv(csv_file, index=False)

        loader = DataLoader(str(csv_file))
        with pytest.raises(DataLoadError, match="重複的時間戳"):
            loader.load()

    def test_get_date_range(self, tmp_path):
        """測試取得日期範圍"""
        csv_file = tmp_path / "test.csv"
        df = pd.DataFrame({
            "datetime": ["2023-01-01 00:00:00", "2023-01-05 00:00:00"],
            "open": [100.0, 101.0],
            "high": [110.0, 111.0],
            "low": [90.0, 91.0],
            "close": [105.0, 106.0],
            "volume": [1000.0, 1100.0],
        })
        df.to_csv(csv_file, index=False)

        loader = DataLoader(str(csv_file))
        loader.load()
        start, end = loader.get_date_range()

        assert start is not None
        assert end is not None


class TestLoadCsv:
    """測試便捷函數"""

    def test_load_csv_function(self, tmp_path):
        """測試 load_csv 函數"""
        csv_file = tmp_path / "test.csv"
        df = pd.DataFrame({
            "datetime": ["2023-01-01 00:00:00"],
            "open": [100.0],
            "high": [110.0],
            "low": [90.0],
            "close": [105.0],
            "volume": [1000.0],
        })
        df.to_csv(csv_file, index=False)

        result = load_csv(str(csv_file))
        assert len(result) == 1

    def test_load_csv_file_not_found(self):
        """測試檔案不存在"""
        with pytest.raises(DataLoadError, match="檔案不存在"):
            load_csv("nonexistent.csv")
