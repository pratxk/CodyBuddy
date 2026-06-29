"""
Symmetric encryption for at-rest secrets (e.g. a user's GitHub PAT).

Uses Fernet (AES-128-CBC + HMAC) with the key from env APP_ENCRYPTION_KEY.
ponytail: if the key is missing we RAISE rather than silently storing plaintext —
a secret must never hit the DB unencrypted.
"""
import os

from cryptography.fernet import Fernet

_ENV_KEY = "APP_ENCRYPTION_KEY"


def _fernet() -> Fernet:
    key = os.environ.get(_ENV_KEY)
    if not key:
        raise RuntimeError(
            f"{_ENV_KEY} is not set — cannot encrypt/decrypt secrets. "
            "Set a Fernet key (Fernet.generate_key()) in the environment."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(plaintext: str) -> str:
    """Encrypt a UTF-8 string; returns a URL-safe base64 token (str)."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypt a token produced by encrypt(); returns the original string."""
    return _fernet().decrypt(token.encode()).decode()
