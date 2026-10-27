"""Encrypt GitHub tokens at rest using Fernet."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


def _derive_fernet_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_token(plaintext: str, encryption_key: str) -> str:
    if not encryption_key:
        raise ValueError("TOKEN_ENCRYPTION_KEY is required to store tokens")
    f = Fernet(_derive_fernet_key(encryption_key))
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_token(ciphertext: str, encryption_key: str) -> str:
    if not encryption_key:
        raise ValueError("TOKEN_ENCRYPTION_KEY is required to read tokens")
    f = Fernet(_derive_fernet_key(encryption_key))
    try:
        return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Invalid encrypted token") from exc
