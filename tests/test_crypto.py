"""
Tests for auth/crypto.py — Fernet encrypt/decrypt. Uses the .env APP_ENCRYPTION_KEY.
"""
import importlib

import pytest

from auth import crypto


def test_encrypt_decrypt_round_trip():
    secret = "ghp_abcdEFGH1234567890example"
    enc = crypto.encrypt(secret)
    assert enc != secret           # actually encrypted, not plaintext
    assert crypto.decrypt(enc) == secret


def test_encrypt_is_non_deterministic():
    # Fernet embeds a random IV → two encryptions of the same value differ.
    a = crypto.encrypt("same-value")
    b = crypto.encrypt("same-value")
    assert a != b
    assert crypto.decrypt(a) == crypto.decrypt(b) == "same-value"


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("APP_ENCRYPTION_KEY", raising=False)
    with pytest.raises(RuntimeError):
        crypto.encrypt("x")
