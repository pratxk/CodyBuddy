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
# Cloudflare Workers AI uses an OpenAI-compatible endpoint whose URL embeds the account id.
_CF_ACCOUNT = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
PROVIDERS: dict[str, dict] = {
    "groq":       {"base_url": "https://api.groq.com/openai/v1",   "api_key_env": "GROQ_API_KEY"},
    "cerebras":   {"base_url": "https://api.cerebras.ai/v1",        "api_key_env": "CEREBRAS_API_KEY"},
    "gemini":     {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                   "api_key_env": "GEMINI_API_KEY"},
    "sambanova":  {"base_url": "https://api.sambanova.ai/v1",       "api_key_env": "SAMBANOVA_API_KEY"},
    "cloudflare": {"base_url": f"https://api.cloudflare.com/client/v4/accounts/{_CF_ACCOUNT}/ai/v1",
                   "api_key_env": "CLOUDFLARE_API_TOKEN"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1",      "api_key_env": "OPENROUTER_API_KEY"},
    "nvidia":     {"base_url": "https://integrate.api.nvidia.com/v1","api_key_env": "NVIDIA_API_KEY"},
}

# Cloudflare GLM is a large reasoning model with slow (60s+) cold starts; give it headroom.
# ponytail: only cloudflare needs the long timeout; others keep the SDK default.
_PROVIDER_TIMEOUT: dict[str, float] = {"cloudflare": 180.0}

# Ordered (provider, model) fallback chains. First with a present key + success wins.
# ponytail: user-requested order — Groq (fast, high TPM) → Cloudflare GLM-5.2 (strong coder,
# but 10k neurons/day + slow cold start, so a fallback not the default drain) → NVIDIA
# (reliable, separate limits) → OpenRouter free (last resort; its free pool 429s often).
# NVIDIA ahead of OpenRouter because OpenRouter's free models are currently rate-limited.
# ponytail: FOUR fast providers up front (Groq 100k/day, Cerebras 1M/day, Gemini ~250-1000
# RPD + 1M ctx, SambaNova fast/low-RPM) so a single provider's cap never drops us to the
# slow tier — only then Cloudflare GLM (quality, 10k neurons/day) → NVIDIA (reliable) →
# OpenRouter (free, flaky). All seven verified live to produce valid Sandpack apps.
PLANNER_CHAIN: list[tuple[str, str]] = [
    ("groq", "llama-3.3-70b-versatile"),
    ("cerebras", "gpt-oss-120b"),
    ("gemini", "gemini-2.5-flash"),
    ("sambanova", "Meta-Llama-3.3-70B-Instruct"),
    ("cloudflare", "@cf/zai-org/glm-5.2"),
    ("nvidia", "meta/llama-3.3-70b-instruct"),
    ("openrouter", "meta-llama/llama-3.3-70b-instruct:free"),
]
# ponytail: coder requests are large (max_tokens=14000 for rich apps) → Groq's 12k TPM 413s,
# so lead with high-capacity providers (Cerebras 1M/day+fast, Gemini 1M-ctx, NVIDIA, GLM).
# Groq is a late fallback (it'll 413 on this size and fall through harmlessly).
CODER_CHAIN: list[tuple[str, str]] = [
    ("cerebras", "gpt-oss-120b"),
    ("gemini", "gemini-2.5-flash"),
    ("nvidia", "meta/llama-3.3-70b-instruct"),
    ("cloudflare", "@cf/zai-org/glm-5.2"),
    ("sambanova", "Meta-Llama-3.3-70B-Instruct"),
    ("groq", "llama-3.3-70b-versatile"),
    ("openrouter", "qwen/qwen3-coder:free"),
]
# ponytail: PREMIUM coder builds run at max_tokens=20000 — drop Groq (12k TPM → 413) and
# OpenRouter free (429s under load). Lead with the highest-capacity providers that can serve
# 20k: Cerebras (1M/day, fast) → NVIDIA (reliable) → Cloudflare GLM (strong, slow) → Gemini
# (1M ctx) → SambaNova. All can return a 20k-token response without truncating the file set.
CODER_CHAIN_PREMIUM: list[tuple[str, str]] = [
    ("cerebras", "gpt-oss-120b"),
    ("nvidia", "meta/llama-3.3-70b-instruct"),
    ("cloudflare", "@cf/zai-org/glm-5.2"),
    ("gemini", "gemini-2.5-flash"),
    ("sambanova", "Meta-Llama-3.3-70B-Instruct"),
]
# ponytail: Gemini 2.5 Flash is free + MULTIMODAL — the only vision-capable model in the pool,
# so the vision chain is gemini-only (no second fallback that's verified to accept image_url).
VISION_CHAIN: list[tuple[str, str]] = [("gemini", "gemini-2.5-flash")]

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
        if provider == "cloudflare" and not _CF_ACCOUNT:
            raise RuntimeError("CLOUDFLARE_ACCOUNT_ID not set for provider cloudflare")
        _clients[provider] = OpenAI(
            base_url=cfg["base_url"], api_key=key,
            timeout=_PROVIDER_TIMEOUT.get(provider, 120.0),
        )
    return _clients[provider]


def _provider_ready(p: str) -> bool:
    if not os.environ.get(PROVIDERS[p]["api_key_env"]):
        return False
    if p == "cloudflare" and not _CF_ACCOUNT:  # token without account id is unusable
        return False
    return True


def usable_chain(chain: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Drop chain entries whose provider is not fully configured (key, and for CF, account)."""
    return [(p, m) for (p, m) in chain if _provider_ready(p)]


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


def chat_vision(
    prompt: str,
    image_data_url: str,
    *,
    chain: list[tuple[str, str]] | None = None,
    system: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.2,
) -> str:
    """Multimodal chat — sends a text prompt + an image (base64 data URL) to a vision model.

    Builds OpenAI-compatible multimodal `content` (text part + image_url part) and reuses the
    same provider-fallback + error handling as chat(). Defaults to VISION_CHAIN (Gemini 2.5
    Flash — free + multimodal).
    """
    chain = usable_chain(chain or VISION_CHAIN)
    if not chain:
        raise AllProvidersFailed("No vision provider has an API key configured")

    messages: list = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image_data_url}},
        ],
    })

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
            logger.warning("Vision provider %s/%s failed: %s — falling back", provider, model, exc)
            continue
    raise AllProvidersFailed(f"All vision providers failed: {last_err}")


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
