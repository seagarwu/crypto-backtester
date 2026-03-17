from agents.strategy_agent import StrategyAgent
from agents.backtest_runner_agent import BacktestRunnerAgent


class TestAgentContext:
    def test_strategy_agent_loads_agent_specific_rules(self):
        agent = StrategyAgent()

        assert "Strategy Agent Rules" in agent.agent_context
        assert "Tool Capabilities" in agent.agent_context

    def test_backtest_runner_loads_agent_specific_rules(self):
        agent = BacktestRunnerAgent(data_dir="data")

        assert "Backtest Agent Rules" in agent.agent_context
        assert "canonical research artifacts" in agent.agent_context
