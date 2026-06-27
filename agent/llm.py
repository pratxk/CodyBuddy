"""
LLM access for CodyBuddy — reliable + fast.

Talks to an OpenAI-compatible endpoint directly (no LangChain `with_structured_output`,
which forces fragile tool/json-schema mode), prompts for plain JSON / raw text, and
parses robustly. This is the NourishBot pattern, plus a provider switch so we can use
Groq's LPU inference (≈5–10× faster per token than NVIDIA NIM) for the same Llama models.

Provider is chosen by env:
    LLM_PROVIDER = groq | nvidia      (default: groq if GROQ_API_KEY is set, else nvidia)
Model overrides:
    PLANNER_MODEL, CODER_MODEL
"""
import json
import logging
import os
import re
import time
from typing import Type, TypeVar

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ValidationError

# Load .env before resolving provider/model config below (import order matters).
load_dotenv()

logger = logging.getLogger(__name__)

# ── Provider configuration ──────────────────────────────────────────────────────
_PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "default_model": "llama-3.3-70b-versatile",
    },
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "api_key_env": "NVIDIA_API_KEY",
        "default_model": "meta/llama-3.1-70b-instruct",
    },
}


def _provider() -> str:
    explicit = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if explicit in _PROVIDERS:
        return explicit
    if os.environ.get("GROQ_API_KEY"):
        return "groq"
    return "nvidia"


def _default_model() -> str:
    return _PROVIDERS[_provider()]["default_model"]


PLANNER_MODEL = os.environ.get("PLANNER_MODEL", "") or _default_model()
CODER_MODEL = os.environ.get("CODER_MODEL", "") or _default_model()

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        cfg = _PROVIDERS[_provider()]
        api_key = os.environ.get(cfg["api_key_env"])
        if not api_key:
            raise RuntimeError(
                f"{cfg['api_key_env']} is not set in the environment / .env "
                f"(LLM_PROVIDER={_provider()})"
            )
        _client = OpenAI(base_url=cfg["base_url"], api_key=api_key)
        logger.info("LLM provider: %s", _provider())
    return _client


def chat(
    prompt: str,
    *,
    model: str | None = None,
    system: str | None = None,
    max_tokens: int = 2048,
    temperature: float = 0.2,
) -> str:
    """Single completion. Returns the stripped text content."""
    messages: list = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = get_client().chat.completions.create(
        model=model or PLANNER_MODEL,
        messages=messages,  # type: ignore[arg-type]
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return (resp.choices[0].message.content or "").strip()


# ── Output cleaning ─────────────────────────────────────────────────────────────

_FENCE_OPEN_RE = re.compile(r"^```[a-zA-Z0-9_+-]*\s*\n?")


def parse_json(raw: str) -> dict:
    """Extract the first valid JSON object from an LLM response (strips prose/fences)."""
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(cleaned[start : end + 1])
    raise ValueError("No JSON object found in model output")


def strip_code_fences(raw: str) -> str:
    """Return a code body with any wrapping ```lang ... ``` fence removed."""
    text = raw.strip()
    if text.startswith("```"):
        text = _FENCE_OPEN_RE.sub("", text, count=1)
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip() + "\n"


# ── Validating structured output with retry ─────────────────────────────────────

T = TypeVar("T", bound=BaseModel)


def chat_structured(
    prompt: str,
    schema: Type[T],
    *,
    model: str | None = None,
    system: str | None = None,
    max_tokens: int = 2048,
    retries: int = 3,
) -> T:
    """Prompt for JSON, parse, and validate against `schema`. Retries with a hint."""
    last_err: Exception | None = None
    current_prompt = prompt
    for attempt in range(1, retries + 1):
        try:
            raw = chat(
                current_prompt,
                model=model,
                system=system,
                max_tokens=max_tokens,
                temperature=0.1,
            )
            return schema.model_validate(parse_json(raw))
        except (ValueError, ValidationError, json.JSONDecodeError) as exc:
            last_err = exc
            logger.warning("Structured output attempt %d/%d failed: %s", attempt, retries, exc)
            current_prompt = (
                f"{prompt}\n\nYour previous response was INVALID: {exc}\n"
                "Respond with ONLY a single valid JSON object matching the required "
                "schema. No prose, no explanations, no markdown code fences."
            )
            time.sleep(0.4 * attempt)
    raise RuntimeError(
        f"Failed to get valid {schema.__name__} after {retries} attempts: {last_err}"
    )
