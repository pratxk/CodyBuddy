"""
LLM access for CodyBuddy — reliable + fast.

Talks to an OpenAI-compatible endpoint directly (no LangChain `with_structured_output`,
which forces fragile tool/json-schema mode), prompts for plain JSON / raw text, and
parses robustly. This is the NourishBot pattern, plus a provider-fallback chain so free-tier
rate limits never hard-fail a build.

Provider fallback chains:
    PLANNER_CHAIN: ordered (provider, model) — first with a present key + success wins
    CODER_CHAIN: ordered (provider, model) — first with a present key + success wins
"""
import json
import logging
import os
import re
import time
from typing import Type, TypeVar

from dotenv import load_dotenv
from openai import APIConnectionError, APIError, OpenAI, RateLimitError
from pydantic import BaseModel, ValidationError

# Load .env before resolving provider/model config below (import order matters).
load_dotenv()

logger = logging.getLogger(__name__)

# ── Provider configuration ──────────────────────────────────────────────────────
PROVIDERS: dict[str, dict] = {
    "groq":       {"base_url": "https://api.groq.com/openai/v1",   "api_key_env": "GROQ_API_KEY"},
    "cerebras":   {"base_url": "https://api.cerebras.ai/v1",        "api_key_env": "CEREBRAS_API_KEY"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1",      "api_key_env": "OPENROUTER_API_KEY"},
    "nvidia":     {"base_url": "https://integrate.api.nvidia.com/v1","api_key_env": "NVIDIA_API_KEY"},
}

# Ordered (provider, model) fallback chains. First with a present key + success wins.
# ponytail: only Groq is verified working on the current keys — the Cerebras model ids
# 404 (key tier lacks access) and the OpenRouter key is invalid (401). So the chains are
# Groq-only with real cross-model fallback; re-add other providers when their keys/models
# are confirmed live.
PLANNER_CHAIN: list[tuple[str, str]] = [
    ("groq", "llama-3.3-70b-versatile"),
    ("groq", "openai/gpt-oss-120b"),
    ("groq", "llama-3.1-8b-instant"),
]
CODER_CHAIN: list[tuple[str, str]] = [
    # ponytail: high-TPM models only — the single-pass coder request is large, so a
    # low-TPM model (llama-3.1-8b-instant, 6000 TPM) can never serve it (always 413).
    ("groq", "llama-3.3-70b-versatile"),
    ("groq", "openai/gpt-oss-120b"),
    ("groq", "qwen/qwen3-32b"),
]

_RETRYABLE = (RateLimitError, APIError, APIConnectionError)
_clients: dict[str, OpenAI] = {}


class AllProvidersFailed(RuntimeError):
    pass


def get_client(provider: str) -> OpenAI:
    if provider not in _clients:
        cfg = PROVIDERS[provider]
        key = os.environ.get(cfg["api_key_env"])
        if not key:
            raise RuntimeError(f"{cfg['api_key_env']} not set for provider {provider}")
        _clients[provider] = OpenAI(base_url=cfg["base_url"], api_key=key)
    return _clients[provider]


def usable_chain(chain: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Drop chain entries whose provider has no API key in the environment."""
    return [
        (p, m) for (p, m) in chain
        if os.environ.get(PROVIDERS[p]["api_key_env"])
    ]


def chat(
    prompt: str,
    *,
    chain: list[tuple[str, str]] | None = None,
    system: str | None = None,
    max_tokens: int = 2048,
    temperature: float = 0.2,
) -> str:
    chain = usable_chain(chain or PLANNER_CHAIN)
    if not chain:
        raise AllProvidersFailed("No provider has an API key configured")

    messages: list = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last_err: Exception | None = None
    for provider, model in chain:
        try:
            resp = get_client(provider).chat.completions.create(
                model=model, messages=messages,  # type: ignore[arg-type]
                max_tokens=max_tokens, temperature=temperature,
            )
            return (resp.choices[0].message.content or "").strip()
        except _RETRYABLE as exc:
            last_err = exc
            logger.warning("Provider %s/%s failed: %s — falling back", provider, model, exc)
            continue
    raise AllProvidersFailed(f"All providers failed: {last_err}")


_FENCE_OPEN_RE = re.compile(r"^```[a-zA-Z0-9_+-]*\s*\n?")


def parse_json(raw: str) -> dict:
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(cleaned[start : end + 1])
    raise ValueError("No JSON object found in model output")


def strip_code_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = _FENCE_OPEN_RE.sub("", text, count=1)
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip() + "\n"


T = TypeVar("T", bound=BaseModel)


def chat_structured(
    prompt: str,
    schema: Type[T],
    *,
    chain: list[tuple[str, str]] | None = None,
    system: str | None = None,
    max_tokens: int = 2048,
    retries: int = 3,
) -> T:
    last_err: Exception | None = None
    current = prompt
    for attempt in range(1, retries + 1):
        try:
            raw = chat(current, chain=chain, system=system,
                       max_tokens=max_tokens, temperature=0.1)
            return schema.model_validate(parse_json(raw))
        except (ValueError, ValidationError, json.JSONDecodeError) as exc:
            last_err = exc
            logger.warning("Structured attempt %d/%d failed: %s", attempt, retries, exc)
            current = (
                f"{prompt}\n\nYour previous response was INVALID: {exc}\n"
                "Respond with ONLY a single valid JSON object matching the schema. "
                "No prose, no markdown."
            )
            time.sleep(0.4 * attempt)
    raise RuntimeError(f"Failed to get valid {schema.__name__}: {last_err}")
