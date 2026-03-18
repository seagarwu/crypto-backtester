#!/usr/bin/env python3
"""Thin backend abstraction for engineer-code generation paths."""

from __future__ import annotations

import asyncio
import importlib
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

try:
    from langchain_core.messages import HumanMessage, SystemMessage
except ModuleNotFoundError:
    HumanMessage = None
    SystemMessage = None


@dataclass
class EngineerBackendRequest:
    model: str
    system_prompt: str
    user_prompt: str
    temperature: float
    max_tokens: int = 2000


@dataclass
class EngineerBackendResponse:
    backend_name: str
    raw_response: str
    request_metadata: Dict[str, Any] = field(default_factory=dict)
    response_metadata: Dict[str, Any] = field(default_factory=dict)


class EngineerBackend:
    name = "base"

    def generate(self, request: EngineerBackendRequest) -> EngineerBackendResponse:
        raise NotImplementedError


class OpenAICompatibleEngineerBackend(EngineerBackend):
    name = "openai_compatible"

    def __init__(self, llm: Any):
        self.llm = llm

    def generate(self, request: EngineerBackendRequest) -> EngineerBackendResponse:
        payload: Any
        if SystemMessage is None or HumanMessage is None:
            payload = f"{request.system_prompt}\n\n{request.user_prompt}".strip()
        else:
            payload = [
                SystemMessage(content=request.system_prompt),
                HumanMessage(content=request.user_prompt),
            ]

        response = self.llm.invoke(payload)
        raw = response.content if hasattr(response, "content") else str(response)
        response_metadata = {}
        if hasattr(response, "response_metadata"):
            response_metadata["response_metadata"] = dict(getattr(response, "response_metadata") or {})
        if hasattr(response, "usage_metadata"):
            response_metadata["usage_metadata"] = dict(getattr(response, "usage_metadata") or {})

        return EngineerBackendResponse(
            backend_name=self.name,
            raw_response=raw,
            request_metadata={
                "path": "openai_compatible_chat",
                "model": request.model,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "message_mode": "system_plus_human" if isinstance(payload, list) else "combined_prompt",
            },
            response_metadata=response_metadata,
        )


class GoogleGenAIEngineerBackend(EngineerBackend):
    name = "google_genai"

    def __init__(self):
        self.genai = importlib.import_module("google.genai")
        self.types = importlib.import_module("google.genai.types")

    def generate(self, request: EngineerBackendRequest) -> EngineerBackendResponse:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")

        client = self.genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=request.model,
            contents=request.user_prompt,
            config=self.types.GenerateContentConfig(
                system_instruction=request.system_prompt,
                temperature=request.temperature,
                top_p=0.95,
                max_output_tokens=request.max_tokens,
            ),
        )
        raw = getattr(response, "text", "") or ""

        response_metadata: Dict[str, Any] = {"path": "google_generate_content"}
        candidates = getattr(response, "candidates", None)
        if candidates:
            first = candidates[0]
            response_metadata["candidate_count"] = len(candidates)
            finish_reason = getattr(first, "finish_reason", None)
            if finish_reason is not None:
                response_metadata["finish_reason"] = str(finish_reason)

        return EngineerBackendResponse(
            backend_name=self.name,
            raw_response=raw,
            request_metadata={
                "path": "google_generate_content",
                "model": request.model,
                "temperature": request.temperature,
                "max_output_tokens": request.max_tokens,
                "system_instruction": True,
            },
            response_metadata=response_metadata,
        )


class GeminiMCPEngineerBackend(EngineerBackend):
    name = "third_party_mcp_stdio"

    def __init__(self):
        mcp_module = importlib.import_module("mcp")
        mcp_stdio = importlib.import_module("mcp.client.stdio")
        self.ClientSession = getattr(mcp_module, "ClientSession")
        self.StdioServerParameters = getattr(mcp_module, "StdioServerParameters")
        self.stdio_client = getattr(mcp_stdio, "stdio_client")

    async def _generate_async(self, request: EngineerBackendRequest) -> EngineerBackendResponse:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")

        params = self.StdioServerParameters(
            command="npx",
            args=["-y", "github:aliargun/mcp-server-gemini"],
            env={"GEMINI_API_KEY": api_key},
        )
        async with self.stdio_client(params) as (read, write):
            async with self.ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "generate_text",
                    arguments={
                        "prompt": request.user_prompt,
                        "model": request.model,
                        "systemInstruction": request.system_prompt,
                        "temperature": request.temperature,
                        "maxTokens": request.max_tokens,
                        "topP": 0.95,
                    },
                )
                raw = ""
                if getattr(result, "content", None):
                    raw = getattr(result.content[0], "text", "") or ""
                return EngineerBackendResponse(
                    backend_name=self.name,
                    raw_response=raw,
                    request_metadata={
                        "path": "mcp_stdio_generate_text",
                        "server": "aliargun/mcp-server-gemini",
                        "tool": "generate_text",
                        "model": request.model,
                        "temperature": request.temperature,
                        "maxTokens": request.max_tokens,
                    },
                    response_metadata=dict(getattr(result, "metadata", None) or {}),
                )

    def generate(self, request: EngineerBackendRequest) -> EngineerBackendResponse:
        return asyncio.run(self._generate_async(request))


def get_engineer_backend(
    backend_name: str,
    llm: Any = None,
) -> EngineerBackend:
    normalized = (backend_name or "openai_compatible").strip().lower()
    if normalized == "openai_compatible":
        if llm is None:
            raise ValueError("llm is required for openai_compatible backend")
        return OpenAICompatibleEngineerBackend(llm)
    if normalized == "google_genai":
        return GoogleGenAIEngineerBackend()
    if normalized in {"third_party_mcp_stdio", "gemini_mcp"}:
        return GeminiMCPEngineerBackend()
    raise ValueError(f"Unknown engineer backend: {backend_name}")
