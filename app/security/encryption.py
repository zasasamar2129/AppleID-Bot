from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class EncryptionService:
    """AES-256-GCM authenticated encryption service."""

    def __init__(self, key: str):
        # Derive a 32-byte key from the provided string using PBKDF2
        salt = b"apple_store_bot_salt"  # Fixed salt for key derivation
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        self._key = kdf.derive(key.encode("utf-8"))
        self._aesgcm = AESGCM(self._key)

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
