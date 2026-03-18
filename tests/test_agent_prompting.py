from agents.agent_prompting import (
    build_agent_context,
    build_engineer_system_prompt,
    load_agent_instructions,
    load_repo_rules,
)


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
        assert "## Workflow Hints" in content
        assert "canonical research artifacts" in content

    def test_load_repo_rules_returns_operational_guidance(self):
        content = load_repo_rules()

        assert "Global Workflow Rules" in content
        assert "Canonical Research Artifacts" in content
        assert "human-in-the-loop" in content

    def test_build_agent_context_includes_agent_specific_workflow_hints(self):
        engineer_content = build_agent_context("engineer_agent")
        reporter_content = build_agent_context("reporter_agent")

        assert "validation failures as the primary input" in engineer_content
        assert "Highlight unresolved risks and human overrides" in reporter_content

    def test_build_engineer_system_prompt_includes_bootstrap_files(self):
        content = build_engineer_system_prompt()

        assert "## Identity" in content
        assert "## Bootstrap Files" in content
        assert "strategies/base.py" in content
        assert "strategies/ma_crossover.py" in content
        assert "remote engineer model cannot directly use MCP tools" in content

    def test_build_engineer_system_prompt_openhands_variant_includes_safety_checks(self):
        content = build_engineer_system_prompt(style="openhands_inspired")

        assert "cautious Python quant-strategy engineer" in content
        assert "Avoid look-ahead bias" in content
        assert "Inside <CODE>, output one complete Python file" in content

    def test_build_engineer_system_prompt_compact_variant_is_shorter(self):
        default = build_engineer_system_prompt(style="default")
        compact = build_engineer_system_prompt(style="compact")

        assert "Return one repo-valid strategy file" in compact
        assert len(compact) < len(default)
