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
from typing import Callable, Type, TypeVar

from dotenv import load_dotenv
from openai import APIConnectionError, APIError, OpenAI, RateLimitError
from pydantic import BaseModel, ValidationError

# Load .env before resolving provider/model config below (import order matters).
load_dotenv()

logger = logging.getLogger(__name__)


def _log(agent, kind, provider, model, t0, ok, error, prompt, response) -> None:
    """Best-effort observability record for one LLM call (never raises)."""
    try:
        from db.ai_logs import log_ai_call
        log_ai_call(
            agent=agent, kind=kind, provider=provider, model=model,
            latency_ms=int((time.monotonic() - t0) * 1000),
            ok=ok, error=error, prompt=prompt, response=response,
        )
    except Exception:  # noqa: BLE001
        pass

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
    "tokenrouter": {"base_url": "https://api.tokenrouter.com/v1",      "api_key_env": "TOKENROUTER_API_KEY"},
    "opencode":   {"base_url": "https://opencode.ai/zen/v1",          "api_key_env": "OPENCODE_API_KEY"},
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
# 2026-11-25 cleanup (each replacement verified live against that provider's model list):
# removed dead ids — OpenRouter llama-3.3-70b-instruct:free + qwen3-coder:free, SambaNova
# Meta-Llama-3.3-70B-Instruct, NVIDIA meta/llama-3.3-70b-instruct (all delisted).
# Added TokenRouter + OpenCode (OpenAI-compatible, free DeepSeek V4.1 Flash; the TokenRouter
# key was tested live 2026-11-25). Free legs sit after the trusted streamers in CODER_CHAIN
# so live streaming still leads with a trusted provider.
PLANNER_CHAIN: list[tuple[str, str]] = [
    ("groq", "llama-3.3-70b-versatile"),
    ("cerebras", "gpt-oss-120b"),
    ("gemini", "gemini-2.5-flash"),
    ("tokenrouter", "deepseek/deepseek-v4.1-flash-1017-free"),
    ("sambanova", "gpt-oss-120b"),
    ("cloudflare", "@cf/zai-org/glm-5.2"),
    ("nvidia", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"),
    ("opencode", "deepseek-v4.1-flash-free"),
    ("openrouter", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"),
]
# ponytail: coder requests are large (max_tokens=14000 for rich apps) → Groq's 12k TPM 413s,
# so lead with high-capacity providers (Cerebras 1M/day+fast, Gemini 1M-ctx, NVIDIA, GLM).
# Groq is a late fallback (it'll 413 on this size and fall through harmlessly).
CODER_CHAIN: list[tuple[str, str]] = [
    ("cerebras", "gpt-oss-120b"),
    ("gemini", "gemini-2.5-flash"),
    ("nvidia", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"),
    ("cloudflare", "@cf/zai-org/glm-5.2"),
    ("sambanova", "gpt-oss-120b"),
    ("groq", "llama-3.3-70b-versatile"),
    ("tokenrouter", "deepseek/deepseek-v4.1-flash-1017-free"),
    ("opencode", "deepseek-v4.1-flash-free"),
    ("openrouter", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"),
]
# ponytail: PREMIUM coder builds run at max_tokens=20000 — drop Groq (12k TPM → 413) and
# OpenRouter free (429s under load). Lead with the highest-capacity providers that can serve
# 20k: Cerebras (1M/day, fast) → NVIDIA (reliable) → Cloudflare GLM (strong, slow) → Gemini
# (1M ctx) → SambaNova. All can return a 20k-token response without truncating the file set.
CODER_CHAIN_PREMIUM: list[tuple[str, str]] = [
    ("cerebras", "gpt-oss-120b"),
    ("nvidia", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"),
    ("cloudflare", "@cf/zai-org/glm-5.2"),
    ("gemini", "gemini-2.5-flash"),
    ("sambanova", "gpt-oss-120b"),
]
# ponytail: Gemini 2.5 Flash is free + MULTIMODAL — the only vision-capable model in the pool,
# so the vision chain is gemini-only (no second fallback that's verified to accept image_url).
VISION_CHAIN: list[tuple[str, str]] = [("gemini", "gemini-2.5-flash")]

# ponytail: providers whose OpenAI-compatible SSE streaming we trust to behave (clean deltas).
# Cloudflare GLM is excluded — slow 60s+ cold starts make streaming fragile, so we never lead
# the live stream with it (it falls through to non-streaming chat() instead).
_STREAM_TRUSTED: set[str] = {"cerebras", "gemini", "groq", "nvidia", "sambanova", "openrouter"}

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
        client = OpenAI(
            base_url=cfg["base_url"], api_key=key,
            timeout=_PROVIDER_TIMEOUT.get(provider, 120.0),
        )
        # Optional LangSmith tracing — only when a key is set (zero overhead otherwise).
        # The in-app AI Logs work regardless; this adds LangSmith's richer trace UI.
        if os.environ.get("LANGSMITH_API_KEY"):
            try:
                from langsmith.wrappers import wrap_openai
                client = wrap_openai(client)
            except Exception as exc:  # noqa: BLE001 — tracing must never break a build
                logger.debug("LangSmith wrap skipped: %s", exc)
        _clients[provider] = client
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
    agent: str = "",
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
        t0 = time.monotonic()
        try:
            resp = get_client(provider).chat.completions.create(
                model=model, messages=messages,  # type: ignore[arg-type]
                max_tokens=max_tokens, temperature=temperature,
            )
            out = (resp.choices[0].message.content or "").strip()
            _log(agent, "chat", provider, model, t0, True, "", prompt, out)
            return out
        except _RETRYABLE as exc:
            last_err = exc
            _log(agent, "chat", provider, model, t0, False, str(exc), prompt, "")
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
    agent: str = "",
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
        t0 = time.monotonic()
        try:
            resp = get_client(provider).chat.completions.create(
                model=model, messages=messages,  # type: ignore[arg-type]
                max_tokens=max_tokens, temperature=temperature,
            )
            out = (resp.choices[0].message.content or "").strip()
            _log(agent, "vision", provider, model, t0, True, "", prompt, out)
            return out
        except _RETRYABLE as exc:
            last_err = exc
            _log(agent, "vision", provider, model, t0, False, str(exc), prompt, "")
            logger.warning("Vision provider %s/%s failed: %s — falling back", provider, model, exc)
            continue
    raise AllProvidersFailed(f"All vision providers failed: {last_err}")


def chat_stream(
    prompt: str,
    *,
    chain: list[tuple[str, str]] | None = None,
    system: str | None = None,
    max_tokens: int = 2048,
    temperature: float = 0.2,
    on_delta: Callable[[str], None] | None = None,
    agent: str = "",
) -> str:
    """Stream the FIRST usable provider, invoking on_delta per text chunk, and return the
    full accumulated text.

    ponytail: only the first provider is streamed (live coder output for the FE). If it isn't
    a trusted streamer, OR streaming raises/returns nothing, we fall back to the existing
    non-streaming chat() over the rest of the chain — the result is always authoritative.
    """
    chain = usable_chain(chain or CODER_CHAIN)
    if not chain:
        raise AllProvidersFailed("No provider has an API key configured")

    messages: list = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    first_provider, first_model = chain[0]
    fallback_chain = chain
    if first_provider in _STREAM_TRUSTED:
        t0 = time.monotonic()
        try:
            stream = get_client(first_provider).chat.completions.create(
                model=first_model, messages=messages,  # type: ignore[arg-type]
                max_tokens=max_tokens, temperature=temperature, stream=True,
            )
            parts: list[str] = []
            for chunk in stream:
                choices = getattr(chunk, "choices", None) or []
                delta = (getattr(choices[0].delta, "content", None) or "") if choices else ""
                if delta:
                    parts.append(delta)
                    if on_delta:
                        on_delta(delta)
            full = "".join(parts).strip()
            if full:
                _log(agent, "stream", first_provider, first_model, t0, True, "", prompt, full)
                return full
            logger.warning("Streaming %s/%s yielded empty output — falling back", first_provider, first_model)
        except Exception as exc:  # noqa: BLE001  ponytail: any SDK/stream hiccup → non-stream fallback
            _log(agent, "stream", first_provider, first_model, t0, False, str(exc), prompt, "")
            logger.warning("Streaming %s/%s failed: %s — falling back to non-streaming", first_provider, first_model, exc)
        fallback_chain = chain[1:]  # first provider already attempted (and failed)

    if not fallback_chain:
        raise AllProvidersFailed("Streaming provider failed and no fallback provider available")
    return chat(prompt, chain=fallback_chain, system=system,
                max_tokens=max_tokens, temperature=temperature, agent=agent)


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
    agent: str = "",
) -> T:
    last_err: Exception | None = None
    current = prompt
    for attempt in range(1, retries + 1):
        try:
            raw = chat(current, chain=chain, system=system,
                       max_tokens=max_tokens, temperature=0.1, agent=agent)
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
