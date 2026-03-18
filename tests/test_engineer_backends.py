from types import SimpleNamespace

from agents.engineer_backends import (
    EngineerBackendRequest,
    OpenAICompatibleEngineerBackend,
    get_engineer_backend,
)


class FakeLLM:
    def __init__(self):
        self.payload = None

    def invoke(self, payload):
        self.payload = payload
        return SimpleNamespace(content="<CODE>from x import y</CODE>")


def test_get_engineer_backend_returns_openai_compatible_backend():
    backend = get_engineer_backend("openai_compatible", llm=FakeLLM())

    assert backend.name == "openai_compatible"


def test_openai_compatible_backend_returns_request_metadata():
    llm = FakeLLM()
    backend = OpenAICompatibleEngineerBackend(llm)
    result = backend.generate(
        EngineerBackendRequest(
            model="gemini-2.5-pro",
            system_prompt="system",
            user_prompt="user",
            temperature=0.8,
            max_tokens=2000,
        )
    )

    assert result.backend_name == "openai_compatible"
    assert result.request_metadata["path"] == "openai_compatible_chat"
    assert result.request_metadata["model"] == "gemini-2.5-pro"
    assert result.raw_response == "<CODE>from x import y</CODE>"
