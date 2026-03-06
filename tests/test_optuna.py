"""
Optuna Optimization Tests
"""

import pytest
import pandas as pd
import numpy as np

from experiments.optuna_search import (
    suggest_params,
    run_optuna_optimization,
    run_optuna_with_walk_forward,
)
from strategies import MACrossoverStrategy


class TestSuggestParams:
    """Test parameter suggestion"""

    def test_categorical_params(self):
        """Test categorical parameter suggestion"""
        # Create a mock trial
        class MockTrial:
            def __init__(self):
                self.params = {}
                
            def suggest_categorical(self, name, choices):
                self.params[name] = choices[0]
                return choices[0]
        
        trial = MockTrial()
        param_space = {"mode": ["fast", "slow"]}
        
        result = suggest_params(trial, param_space)
        
        assert "mode" in result
        assert result["mode"] in ["fast", "slow"]

    def test_int_params(self):
        """Test integer parameter suggestion"""
        class MockTrial:
            def __init__(self):
                self.params = {}
                
            def suggest_int(self, name, low, high, step=1):
                self.params[name] = low
                return low
        
        trial = MockTrial()
        param_space = {"window": {"low": 10, "high": 50, "type": "int"}}
        
        result = suggest_params(trial, param_space)
        
        assert "window" in result
        assert 10 <= result["window"] <= 50

    def test_float_params(self):
        """Test float parameter suggestion"""
        class MockTrial:
            def __init__(self):
                self.params = {}
                
            def suggest_float(self, name, low, high, log=False):
                self.params[name] = (low + high) / 2
                return (low + high) / 2
        
        trial = MockTrial()
        param_space = {"threshold": {"low": 0.0, "high": 1.0}}
        
        result = suggest_params(trial, param_space)
        
        assert "threshold" in result
        assert 0.0 <= result["threshold"] <= 1.0

    def test_log_uniform_params(self):
        """Test log uniform parameter suggestion"""
        class MockTrial:
            def __init__(self):
                self.params = {}
                
            def suggest_float(self, name, low, high, log=False):
                self.params[name] = np.sqrt(low * high)
                return np.sqrt(low * high)
        
        trial = MockTrial()
        param_space = {"learning_rate": {"low": 0.001, "high": 0.1, "log": True}}
        
        result = suggest_params(trial, param_space)
        
        assert "learning_rate" in result
        assert 0.001 <= result["learning_rate"] <= 0.1


class TestRunOptunaOptimization:
    """Test Optuna optimization"""

    def test_run_optuna_basic(self):
        """Test basic Optuna optimization"""
        # Create test data
        np.random.seed(42)
        n = 500
        data = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=n, freq="h"),
            "open": [100] * n,
            "high": [105] * n,
            "low": [95] * n,
            "close": [100 + i * 0.1 + np.random.randn() * 0.5 for i in range(n)],
            "volume": [1000] * n,
        })

        # Parameter space
        param_space = {
            "short_window": {"low": 5, "high": 20, "type": "int"},
            "long_window": {"low": 20, "high": 50, "type": "int"},
        }

        # Run optimization
        result = run_optuna_optimization(
            data=data,
            strategy_class=MACrossoverStrategy,
            param_space=param_space,
            objective="sharpe_ratio",
            n_trials=10,
            show_progress=False,
        )

        # Verify
        assert "best_params" in result
        assert "best_value" in result
        assert "n_trials" in result
        assert result["n_trials"] == 10
        assert "short_window" in result["best_params"]
        assert "long_window" in result["best_params"]

    def test_run_optuna_with_constraints(self):
        """Test Optuna with parameter constraints"""
        # Create test data
        np.random.seed(42)
        n = 300
        data = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=n, freq="h"),
            "open": [100] * n,
            "high": [105] * n,
            "low": [95] * n,
            "close": list(range(100, 100 + n)),
            "volume": [1000] * n,
        })

        # Parameter space
        param_space = {
            "short_window": {"low": 5, "high": 30, "type": "int"},
            "long_window": {"low": 10, "high": 60, "type": "int"},
        }

        # Constraint: short_window < long_window
        def constraints(params):
            return params["short_window"] < params["long_window"]

        # Run optimization with constraints
        result = run_optuna_optimization(
            data=data,
            strategy_class=MACrossoverStrategy,
            param_space=param_space,
            objective="sharpe_ratio",
            n_trials=15,
            constraints=constraints,
            show_progress=False,
        )

        # Verify constraints are satisfied
        assert result["best_params"]["short_window"] < result["best_params"]["long_window"]

    def test_run_optuna_different_objectives(self):
        """Test Optuna with different objectives"""
        # Create test data
        np.random.seed(42)
        n = 300
        data = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=n, freq="h"),
            "open": [100] * n,
            "high": [105] * n,
            "low": [95] * n,
            "close": list(range(100, 100 + n)),
            "volume": [1000] * n,
        })

        param_space = {
            "short_window": {"low": 5, "high": 15, "type": "int"},
            "long_window": {"low": 20, "high": 40, "type": "int"},
        }

        # Test with total_return objective
        result = run_optuna_optimization(
            data=data,
            strategy_class=MACrossoverStrategy,
            param_space=param_space,
            objective="total_return",
            n_trials=5,
            show_progress=False,
        )

        assert "best_params" in result
        assert result["n_trials"] == 5


class TestRunOptunaWithWalkForward:
    """Test Optuna with Walk-Forward"""

    def test_run_optuna_walk_forward_basic(self):
        """Test basic Optuna walk-forward"""
        # Create test data
        np.random.seed(42)
        n = 1000
        data = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=n, freq="h"),
            "open": [100] * n,
            "high": [105] * n,
            "low": [95] * n,
            "close": [100 + i * 0.1 + np.random.randn() * 0.5 for i in range(n)],
            "volume": [1000] * n,
        })

        param_space = {
            "short_window": {"low": 5, "high": 15, "type": "int"},
            "long_window": {"low": 20, "high": 35, "type": "int"},
        }

        result = run_optuna_with_walk_forward(
            data=data,
            strategy_class=MACrossoverStrategy,
            param_space=param_space,
            train_bars=300,
            test_bars=100,
            step_bars=100,
            n_trials=5,
            show_progress=False,
        )

        # Verify
        assert "folds_results" in result
        assert "stitched_equity" in result
        assert "summary" in result
        assert len(result["folds_results"]) > 0
        assert "test_sharpe_ratio" in result["folds_results"].columns
