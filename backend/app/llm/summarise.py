"""Anthropic client wrappers for the narrative layer.

The LLMClient is an async wrapper around the Anthropic Messages API with two
demo-friendly properties:

1. A small in-memory LRU cache keyed on the prompt hash. Repeated runs during a
   pitch demo return instantly without a second network round-trip.

2. A fixture fallback path. When settings.allow_live_ingest is False the client
   never calls Anthropic and instead returns pre-canned strings loaded from
   data/fixtures/llm_responses.json. This means the demo works without an
   ANTHROPIC_API_KEY and without network access.

Model selection follows the rule given in the project brief:
  - claude-opus-4-8 for synthesis (scenario narratives, recommendations, brief)
  - claude-haiku-4-5-20251001 for high-frequency classification and short
    summarisation (risk summary)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.llm.prompts import (
    SYSTEM_ANALYST,
    build_executive_brief_prompt,
    build_recommendation_prompt,
    build_risk_summary_prompt,
    build_scenario_narrative_prompt,
)

if TYPE_CHECKING:
    from app.engines.models import (
        Commodity,
        RiskScore,
        ScenarioResult,
        SourcingOption,
    )

logger = logging.getLogger(__name__)

_FIXTURE_PATH = Path(__file__).resolve().parents[3] / "data" / "fixtures" / "llm_responses.json"
_CACHE_MAXSIZE = 64
_DEFAULT_MAX_TOKENS = 1024
_BRIEF_MAX_TOKENS = 2048


@lru_cache(maxsize=1)
def _load_fixture_responses() -> dict[str, str]:
    """Load the canned LLM responses bundle. Result is cached for the process."""
    try:
        with _FIXTURE_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError(f"fixture file {_FIXTURE_PATH} is not a JSON object")
        return {str(k): str(v) for k, v in data.items()}
    except FileNotFoundError:
        logger.warning("LLM fixture file missing at %s; returning empty bundle", _FIXTURE_PATH)
        return {}


def _hash_prompt(model: str, system: str, user: str, max_tokens: int) -> str:
    """Deterministic cache key spanning model, system, user prompt and limits."""
    h = hashlib.blake2b(digest_size=16)
    h.update(model.encode("utf-8"))
    h.update(b"\x00")
    h.update(system.encode("utf-8"))
    h.update(b"\x00")
    h.update(user.encode("utf-8"))
    h.update(b"\x00")
    h.update(str(max_tokens).encode("ascii"))
    return h.hexdigest()


class LLMClient:
    """Async Anthropic client with caching and a fixture fallback.

    Construction is cheap: the Anthropic SDK client is created lazily on first
    live call so that the fixture mode does not require the package to be
    importable beyond the dependency declaration in pyproject.toml.

    The class is not thread-safe. Callers should instantiate one per
    application process (FastAPI app state is the natural home) and rely on
    asyncio for concurrency.
    """

    SYNTHESIS_MODEL = "claude-opus-4-8"
    CLASSIFIER_MODEL = "claude-haiku-4-5-20251001"

    def __init__(self, settings: Any | None = None) -> None:
        if settings is None:
            from app.config import get_settings  # local import to avoid a hard dep at import time

            settings = get_settings()
        self._settings = settings
        self._api_key: str | None = getattr(settings, "anthropic_api_key", None)
        self._synthesis_model: str = getattr(settings, "llm_synthesis_model", self.SYNTHESIS_MODEL)
        self._classifier_model: str = getattr(
            settings, "llm_classifier_model", self.CLASSIFIER_MODEL
        )
        self._allow_live: bool = bool(getattr(settings, "allow_live_ingest", False))
        self._cache: OrderedDict[str, str] = OrderedDict()
        self._cache_lock = asyncio.Lock()
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:
            raise RuntimeError(
                "anthropic SDK is not installed but live mode is enabled; "
                "either set ALLOW_LIVE_INGEST=false or install the anthropic package"
            ) from exc
        if not self._api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is unset but live mode is enabled; "
                "either configure the key or set ALLOW_LIVE_INGEST=false"
            )
        self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client

    async def _cache_get(self, key: str) -> str | None:
        async with self._cache_lock:
            value = self._cache.get(key)
            if value is not None:
                self._cache.move_to_end(key)
            return value

    async def _cache_put(self, key: str, value: str) -> None:
        async with self._cache_lock:
            self._cache[key] = value
            self._cache.move_to_end(key)
            while len(self._cache) > _CACHE_MAXSIZE:
                self._cache.popitem(last=False)

    async def _complete(
        self,
        *,
        model: str,
        user_prompt: str,
        fixture_key: str,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        system: str = SYSTEM_ANALYST,
    ) -> str:
        """Shared completion path used by every public method.

        Resolution order:
          1. fixture mode (allow_live_ingest is False) -> return canned text
          2. cache hit  -> return cached completion
          3. live call -> Anthropic Messages API, cache and return
        """
        if not self._allow_live:
            fixtures = _load_fixture_responses()
            canned = fixtures.get(fixture_key)
            if canned is None:
                logger.warning(
                    "no fixture entry for key %s; returning placeholder narrative",
                    fixture_key,
                )
                return (
                    f"[fixture {fixture_key} unavailable] live LLM calls are "
                    "disabled in this environment."
                )
            return canned

        cache_key = _hash_prompt(model, system, user_prompt, max_tokens)
        cached = await self._cache_get(cache_key)
        if cached is not None:
            return cached

        client = self._get_client()
        response = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
        )

        text = _extract_text(response)
        await self._cache_put(cache_key, text)
        return text

    async def summarise_risk(
        self,
        scores: list["RiskScore"],
        events: list[dict[str, Any]],
    ) -> str:
        """Short situational summary across one or more risk scores. Haiku."""
        prompt = build_risk_summary_prompt(scores, events)
        return await self._complete(
            model=self._classifier_model,
            user_prompt=prompt,
            fixture_key="summarise_risk",
            max_tokens=_DEFAULT_MAX_TOKENS,
        )

    async def narrate_scenario(
        self,
        result: "ScenarioResult",
        context: dict[str, Any],
    ) -> str:
        """Executive narrative for a scenario simulation result. Opus."""
        prompt = build_scenario_narrative_prompt(result, context)
        return await self._complete(
            model=self._synthesis_model,
            user_prompt=prompt,
            fixture_key="narrate_scenario",
            max_tokens=_DEFAULT_MAX_TOKENS,
        )

    async def draft_recommendation(
        self,
        commodity: "Commodity",
        options: list["SourcingOption"],
        risk: "RiskScore",
    ) -> str:
        """Procurement recommendation across sourcing options. Opus."""
        prompt = build_recommendation_prompt(commodity, options, risk)
        return await self._complete(
            model=self._synthesis_model,
            user_prompt=prompt,
            fixture_key="draft_recommendation",
            max_tokens=_DEFAULT_MAX_TOKENS,
        )

    async def executive_brief(self, snapshot: dict[str, Any]) -> str:
        """One-page daily executive brief. Opus, larger token budget."""
        prompt = build_executive_brief_prompt(snapshot)
        return await self._complete(
            model=self._synthesis_model,
            user_prompt=prompt,
            fixture_key="executive_brief",
            max_tokens=_BRIEF_MAX_TOKENS,
        )


def _extract_text(response: Any) -> str:
    """Pull plain text out of an Anthropic Messages API response.

    The SDK returns a Message whose content is a list of blocks. We
    concatenate every block of type 'text' in order. Tool-use blocks are
    ignored because the prompts in this module never enable tool use.
    """
    content = getattr(response, "content", None) or []
    parts: list[str] = []
    for block in content:
        block_type = getattr(block, "type", None)
        if block_type == "text":
            text = getattr(block, "text", "")
            if text:
                parts.append(text)
    return "".join(parts).strip()


__all__ = ["LLMClient"]
