from agents.agent_prompting import build_agent_context, load_agent_instructions


class TestAgentPrompting:
    def test_load_agent_instructions_for_engineer(self):
        content = load_agent_instructions("engineer_agent")

        assert "Engineer Agent Rules" in content
        assert "Do not import `pandas_ta`" in content

    def test_build_agent_context_includes_repo_rules_and_tool_capabilities(self):
        content = build_agent_context("engineer_agent")

        assert "## Repo Rules" in content
        assert "## Agent Rules" in content
        assert "## Tool Capabilities" in content
        assert "canonical research artifacts" in content
