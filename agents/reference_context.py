#!/usr/bin/env python3
"""Reference context providers for reference-guided engineer synthesis."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class EngineerReferenceRequest:
    strategy_name: str
    indicators: List[str]
    feedback: Dict[str, Any] = field(default_factory=dict)
    prior_attempts: List[Dict[str, Any]] = field(default_factory=list)
    route_family: str = ""


class EngineerReferenceProvider:
    """Base interface for gathering controlled reference context."""

    provider_name = "base"

    def build(self, request: EngineerReferenceRequest) -> Dict[str, Any]:
        raise NotImplementedError


class RepoPatternReferenceProvider(EngineerReferenceProvider):
    """Reference provider that exposes repo-native strategy patterns."""

    provider_name = "repo_patterns"

    def build(self, request: EngineerReferenceRequest) -> Dict[str, Any]:
        normalized = {
            str(indicator).strip().strip("'\"").lower()
            for indicator in (request.indicators or [])
            if str(indicator).strip()
        }
        references: List[Dict[str, Any]] = []

        if {"bband", "volume"}.issubset(normalized):
            references.append(
                {
                    "source": self.provider_name,
                    "pattern": "multi_timeframe_bband_reversion",
                    "why": "Known repo-native BBand + volume pattern with validated BaseStrategy contract.",
                }
            )
        if "bband" in normalized:
            references.append(
                {
                    "source": self.provider_name,
                    "pattern": "single_timeframe_bband_reversion",
                    "why": "Simple BBand reversion pattern that keeps signal generation compact.",
                }
            )
        if "ma" in normalized or {"ma20", "ma50"}.issubset(normalized):
            references.append(
                {
                    "source": self.provider_name,
                    "pattern": "ma_crossover",
                    "why": "Known repo-native moving-average crossover implementation.",
                }
            )

        repeated_categories = sorted(
            {
                category
                for attempt in request.prior_attempts
                for category in (attempt.get("failure_categories", []) or [])
            }
        )

        result: Dict[str, Any] = {
            "provider": self.provider_name,
            "repo_patterns": references,
            "repeated_failure_categories": repeated_categories,
            "guardrails": [
                "Only use Python stdlib, pandas, numpy, and repo-local modules.",
                "Return a full BaseStrategy subclass with a complete generate_signals implementation and repo-native initialization.",
                "Prefer simple repo-native logic over novel dependencies when failures repeat.",
            ],
        }
        if request.feedback:
            result["feedback_focus"] = request.feedback
        if request.route_family:
            result["route_family"] = request.route_family
        return result


class CachedEngineerReferenceProvider(EngineerReferenceProvider):
    """Read curated external reference summaries from a local cache artifact."""

    provider_name = "reference_cache"

    def __init__(self, cache_path: str):
        self.cache_path = Path(cache_path)

    def build(self, request: EngineerReferenceRequest) -> Dict[str, Any]:
        entries = self._load_entries()
        normalized = {
            str(indicator).strip().strip("'\"").lower()
            for indicator in (request.indicators or [])
            if str(indicator).strip()
        }
        matched: List[Dict[str, Any]] = []
        for entry in entries:
            tags = {
                str(tag).strip().strip("'\"").lower()
                for tag in (entry.get("tags", []) or [])
                if str(tag).strip()
            }
            patterns = {
                str(pattern).strip().strip("'\"").lower()
                for pattern in (entry.get("patterns", []) or [])
                if str(pattern).strip()
            }
            if request.route_family and request.route_family.lower() in patterns:
                matched.append(entry)
                continue
            if normalized.intersection(tags) or normalized.intersection(patterns):
                matched.append(entry)

        return {
            "provider": self.provider_name,
            "external_references": matched,
            "reference_cache_path": str(self.cache_path),
        }

    def _load_entries(self) -> List[Dict[str, Any]]:
        if not self.cache_path.exists():
            return []
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        if isinstance(payload, list):
            return [dict(item) for item in payload]
        return []


class CompositeEngineerReferenceProvider(EngineerReferenceProvider):
    """Merge multiple controlled reference providers into one payload."""

    provider_name = "composite"

    def __init__(self, providers: Optional[Iterable[EngineerReferenceProvider]] = None):
        self.providers = list(providers or [])

    def build(self, request: EngineerReferenceRequest) -> Dict[str, Any]:
        combined: Dict[str, Any] = {
            "sources": [],
            "repo_patterns": [],
            "external_references": [],
            "guardrails": [],
            "repeated_failure_categories": [],
        }
        seen_guardrails = set()
        seen_categories = set()
        for provider in self.providers:
            payload = provider.build(request)
            combined["sources"].append(provider.provider_name)
            combined["repo_patterns"].extend(payload.get("repo_patterns", []) or [])
            combined["external_references"].extend(payload.get("external_references", []) or [])
            for guardrail in payload.get("guardrails", []) or []:
                if guardrail not in seen_guardrails:
                    combined["guardrails"].append(guardrail)
                    seen_guardrails.add(guardrail)
            for category in payload.get("repeated_failure_categories", []) or []:
                if category not in seen_categories:
                    combined["repeated_failure_categories"].append(category)
                    seen_categories.add(category)
            for key, value in payload.items():
                if key in {"provider", "repo_patterns", "external_references", "guardrails", "repeated_failure_categories"}:
                    continue
                combined[key] = value
        return combined
