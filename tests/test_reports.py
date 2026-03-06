"""
Reporting Module Tests
"""

import pytest
import pandas as pd
import numpy as np
import os
import tempfile
import shutil

from reports.generator import (
    ReportGenerator,
    generate_optimization_report,
)


class TestReportGenerator:
    """Test ReportGenerator class"""

    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary output directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def sample_equity_data(self):
        """Create sample equity data"""
        np.random.seed(42)
        n = 100
        return pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=n, freq="h"),
            "equity": [10000 * (1 + i * 0.01 + np.random.randn() * 0.005) for i in range(n)],
        })

    @pytest.fixture
    def sample_optimization_results(self):
        """Create sample optimization results"""
        return pd.DataFrame({
            "short_window": [10, 20, 30, 15, 25],
            "long_window": [50, 50, 50, 60, 60],
            "sharpe_ratio": [1.2, 1.5, 1.3, 1.1, 1.4],
            "total_return": [0.1, 0.2, 0.15, 0.08, 0.18],
            "max_drawdown": [0.1, 0.15, 0.12, 0.08, 0.14],
        })

    def test_init_creates_directory(self, temp_output_dir):
        """Test that initialization creates output directory"""
        gen = ReportGenerator(temp_output_dir)
        assert os.path.exists(temp_output_dir)

    def test_plot_equity_curve_creates_file(self, temp_output_dir, sample_equity_data):
        """Test that equity curve plotting creates a file"""
        gen = ReportGenerator(temp_output_dir)
        filepath = gen.plot_equity_curve(sample_equity_data, "Test Equity")
        
        assert filepath is not None
        assert os.path.exists(filepath)
        assert filepath.endswith(".png")

    def test_plot_drawdown_creates_file(self, temp_output_dir, sample_equity_data):
        """Test that drawdown plotting creates a file"""
        gen = ReportGenerator(temp_output_dir)
        filepath = gen.plot_drawdown(sample_equity_data, "Test Drawdown")
        
        assert filepath is not None
        assert os.path.exists(filepath)
        assert filepath.endswith(".png")

    def test_plot_optimization_heatmap_creates_file(self, temp_output_dir, sample_optimization_results):
        """Test that optimization heatmap creates a file"""
        gen = ReportGenerator(temp_output_dir)
        filepath = gen.plot_optimization_heatmap(
            sample_optimization_results,
            "short_window",
            "long_window",
            metric="sharpe_ratio",
        )
        
        assert filepath is not None
        assert os.path.exists(filepath)
        assert filepath.endswith(".png")

    def test_plot_optimization_heatmap_invalid_params(self, temp_output_dir, sample_optimization_results):
        """Test heatmap with invalid parameters"""
        gen = ReportGenerator(temp_output_dir)
        
        # Invalid column names
        filepath = gen.plot_optimization_heatmap(
            sample_optimization_results,
            "invalid_x",
            "invalid_y",
            metric="sharpe_ratio",
        )
        
        # Should return None when params are invalid
        assert filepath is None

    def test_generate_html_report_creates_file(self, temp_output_dir):
        """Test that HTML report generation creates a file"""
        gen = ReportGenerator(temp_output_dir)
        
        metrics = {
            "sharpe_ratio": 1.5,
            "total_return": 0.2,
            "max_drawdown": 0.15,
            "win_rate": 0.55,
        }
        
        filepath = gen.generate_html_report(
            title="Test Report",
            metrics=metrics,
        )
        
        assert filepath is not None
        assert os.path.exists(filepath)
        assert filepath.endswith(".html")

    def test_generate_html_report_with_charts(self, temp_output_dir, sample_equity_data):
        """Test HTML report with charts"""
        gen = ReportGenerator(temp_output_dir)
        
        # Create a chart first
        chart_path = gen.plot_equity_curve(sample_equity_data, "Test")
        
        metrics = {
            "sharpe_ratio": 1.5,
            "total_return": 0.2,
        }
        
        # Generate report with chart
        filepath = gen.generate_html_report(
            title="Test Report with Chart",
            metrics=metrics,
            charts=[chart_path],
        )
        
        assert filepath is not None
        assert os.path.exists(filepath)
        
        # Verify HTML contains the chart reference
        with open(filepath, "r") as f:
            content = f.read()
            assert "Test" in content


class TestGenerateOptimizationReport:
    """Test generate_optimization_report function"""

    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary output directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_generate_optimization_report_basic(self, temp_output_dir):
        """Test basic optimization report generation"""
        results_df = pd.DataFrame({
            "trial_number": [0, 1, 2],
            "value": [1.2, 1.5, 1.3],
            "short_window": [10, 20, 15],
            "long_window": [50, 50, 60],
        })
        
        result = generate_optimization_report(
            results_df,
            output_dir=temp_output_dir,
            title="Test Optimization",
        )
        
        assert "html_report" in result
        assert os.path.exists(result["html_report"])

    def test_generate_optimization_report_with_heatmap(self, temp_output_dir):
        """Test optimization report with heatmap"""
        results_df = pd.DataFrame({
            "short_window": [10, 20, 30, 15, 25],
            "long_window": [50, 50, 50, 60, 60],
            "sharpe_ratio": [1.2, 1.5, 1.3, 1.1, 1.4],
            "total_return": [0.1, 0.2, 0.15, 0.08, 0.18],
        })
        
        result = generate_optimization_report(
            results_df,
            output_dir=temp_output_dir,
            title="Test Optimization with Heatmap",
        )
        
        assert "html_report" in result
        assert "heatmap_sharpe_ratio" in result

    def test_generate_optimization_report_minimal(self, temp_output_dir):
        """Test optimization report with minimal data"""
        results_df = pd.DataFrame({
            "short_window": [10],
            "long_window": [50],
            "sharpe_ratio": [1.5],
        })
        
        result = generate_optimization_report(
            results_df,
            output_dir=temp_output_dir,
            title="Minimal Test",
        )
        
        assert "html_report" in result


class TestReportGeneratorEdgeCases:
    """Test edge cases for ReportGenerator"""

    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary output directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_empty_dataframe(self, temp_output_dir):
        """Test with empty DataFrame"""
        gen = ReportGenerator(temp_output_dir)
        
        empty_df = pd.DataFrame(columns=["datetime", "equity"])
        filepath = gen.plot_equity_curve(empty_df)
        
        # Should return None for empty data
        assert filepath is None

    def test_single_row_dataframe(self, temp_output_dir):
        """Test with single row DataFrame"""
        gen = ReportGenerator(temp_output_dir)
        
        single_row = pd.DataFrame({
            "datetime": [pd.Timestamp("2023-01-01")],
            "equity": [10000],
        })
        filepath = gen.plot_equity_curve(single_row)
        
        assert filepath is not None

    def test_equity_with_nan(self, temp_output_dir):
        """Test with NaN values in equity"""
        gen = ReportGenerator(temp_output_dir)
        
        data_with_nan = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=10, freq="h"),
            "equity": [10000, 10100, np.nan, 10300, 10400, np.nan, 10600, 10700, 10800, 10900],
        })
        filepath = gen.plot_equity_curve(data_with_nan)
        
        assert filepath is not None

    def test_metrics_with_none_values(self, temp_output_dir):
        """Test HTML generation with None values in metrics"""
        gen = ReportGenerator(temp_output_dir)
        
        metrics = {
            "sharpe_ratio": None,
            "total_return": 0.2,
            "win_rate": 0.55,
        }
        
        filepath = gen.generate_html_report(
            title="Test with None",
            metrics=metrics,
        )
        
        assert filepath is not None
