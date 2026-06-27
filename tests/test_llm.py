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
