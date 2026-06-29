import pytest
from unittest.mock import MagicMock
import agent.llm as llm


def _fake_completion(text):
    msg = MagicMock(); msg.content = text
    choice = MagicMock(); choice.message = msg
    resp = MagicMock(); resp.choices = [choice]
    return resp


def test_chat_falls_back_to_second_provider(monkeypatch):
    from openai import RateLimitError
    calls = []

    class FakeClient:
        def __init__(self, name): self.name = name
        @property
        def chat(self): return self
        @property
        def completions(self): return self
        def create(self, **kw):
            calls.append(kw["model"])
            if kw["model"] == "model-a":
                raise RateLimitError("rate limited", response=MagicMock(status_code=429), body=None)
            return _fake_completion("hello from b")

    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setenv("CEREBRAS_API_KEY", "y")
    monkeypatch.setattr(llm, "get_client", lambda provider: FakeClient(provider))
    out = llm.chat("hi", chain=[("groq", "model-a"), ("cerebras", "model-b")])
    assert out == "hello from b"
    assert calls == ["model-a", "model-b"]


def test_chat_raises_when_all_fail(monkeypatch):
    from openai import APIError

    class FakeClient:
        @property
        def chat(self): return self
        @property
        def completions(self): return self
        def create(self, **kw):
            raise APIError("boom", request=MagicMock(), body=None)

    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setenv("CEREBRAS_API_KEY", "y")
    monkeypatch.setattr(llm, "get_client", lambda provider: FakeClient())
    with pytest.raises(llm.AllProvidersFailed):
        llm.chat("hi", chain=[("groq", "m1"), ("cerebras", "m2")])


def test_chain_skips_provider_with_missing_key(monkeypatch):
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "x")
    chain = llm.usable_chain([("cerebras", "m1"), ("groq", "m2")])
    assert chain == [("groq", "m2")]


# ── chat_stream ──────────────────────────────────────────────────────────────

def _stream_chunk(text):
    delta = MagicMock(); delta.content = text
    choice = MagicMock(); choice.delta = delta
    chunk = MagicMock(); chunk.choices = [choice]
    return chunk


def test_chat_stream_calls_on_delta_and_joins(monkeypatch):
    pieces = ["Hello ", "from ", "stream"]

    class FakeClient:
        @property
        def chat(self): return self
        @property
        def completions(self): return self
        def create(self, **kw):
            assert kw.get("stream") is True
            return iter(_stream_chunk(p) for p in pieces)

    monkeypatch.setenv("CEREBRAS_API_KEY", "y")
    monkeypatch.setattr(llm, "get_client", lambda provider: FakeClient())

    seen: list[str] = []
    out = llm.chat_stream("hi", chain=[("cerebras", "m1")], on_delta=seen.append)
    assert out == "Hello from stream"
    assert seen == pieces


def test_chat_stream_falls_back_to_non_streaming_on_error(monkeypatch):
    from openai import APIError

    class FakeClient:
        @property
        def chat(self): return self
        @property
        def completions(self): return self
        def create(self, **kw):
            if kw.get("stream"):
                raise APIError("stream boom", request=MagicMock(), body=None)
            return _fake_completion("non-stream result")

    monkeypatch.setenv("CEREBRAS_API_KEY", "y")
    monkeypatch.setenv("NVIDIA_API_KEY", "z")
    monkeypatch.setattr(llm, "get_client", lambda provider: FakeClient())

    seen: list[str] = []
    out = llm.chat_stream(
        "hi",
        chain=[("cerebras", "m1"), ("nvidia", "m2")],
        on_delta=seen.append,
    )
    assert out == "non-stream result"
    assert seen == []  # nothing streamed before the failure


def test_chat_stream_skips_streaming_for_untrusted_provider(monkeypatch):
    """Cloudflare isn't a trusted streamer → go straight to non-streaming chat()."""
    seen_stream = []

    class FakeClient:
        @property
        def chat(self): return self
        @property
        def completions(self): return self
        def create(self, **kw):
            seen_stream.append(kw.get("stream"))
            return _fake_completion("cf non-stream")

    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "t")
    monkeypatch.setattr(llm, "_CF_ACCOUNT", "acct")  # _provider_ready checks this module global
    monkeypatch.setattr(llm, "get_client", lambda provider: FakeClient())
    out = llm.chat_stream("hi", chain=[("cloudflare", "glm")], on_delta=lambda d: None)
    assert out == "cf non-stream"
    # streaming was never attempted (no stream=True call)
    assert True not in seen_stream
