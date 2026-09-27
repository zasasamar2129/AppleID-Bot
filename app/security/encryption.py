from __future__ import annotations

import base64
import os
import threading

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class EncryptionService:
    """AES-256-GCM authenticated encryption service.

    Key derivation (PBKDF2-SHA256, 100k iterations) costs ~50-70ms of pure
    CPU. It depends only on the configured key, so it is derived once per
    process and cached. ``__init__`` therefore performs no expensive work and
    is safe to call from hot paths (per-request, per-job) without blocking
    the event loop for tens of milliseconds.
    """

    _key_cache: dict[str, bytes] = {}
    _cache_lock = threading.Lock()

    def __init__(self, key: str):
        self._key = self._derive_key(key)
        self._aesgcm = AESGCM(self._key)

    @classmethod
    def _derive_key(cls, key: str) -> bytes:
        cached = cls._key_cache.get(key)
        if cached is not None:
            return cached
        # Fixed salt for key derivation: the ENCRYPTION_KEY itself must be
        # high-entropy (see scripts/setup_database.py / SETUP docs). A fixed
        # salt is acceptable here because the derived key is a deployment-wide
        # secret, not a password.
        salt = b"apple_store_bot_salt"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        derived = kdf.derive(key.encode("utf-8"))
        with cls._cache_lock:
            cls._key_cache.setdefault(key, derived)
            return cls._key_cache[key]

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string and return base64-encoded ciphertext (including nonce)."""
        nonce = os.urandom(12)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        # Combine nonce + ciphertext
        combined = nonce + ciphertext
        return base64.b64encode(combined).decode("utf-8")

    def decrypt(self, encrypted: str) -> str:
        """Decrypt a base64-encoded ciphertext (nonce included)."""
        combined = base64.b64decode(encrypted.encode("utf-8"))
        nonce = combined[:12]
        ciphertext = combined[12:]
        plaintext = self._aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")
