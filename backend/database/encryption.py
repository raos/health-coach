"""
Field-level encryption for sensitive database columns.

Algorithm: AES-256-GCM with a random 12-byte nonce per encryption.
Stored format: "enc:v1:<base64(nonce + ciphertext + tag)>"

The "enc:v1:" prefix lets decrypt_value gracefully handle plaintext
values that predate encryption (they are returned as-is), making
zero-downtime migrations possible.

Lookup: mcp_api_key cannot be equality-queried after encryption because
each encryption produces a different ciphertext. Use hmac_lookup() to
compute a deterministic HMAC-SHA256 and store it in the companion
*_lookup column; query that column instead.
"""
import os
import base64
import hmac as _hmac
import hashlib
from typing import Optional

from sqlalchemy import types


_PREFIX = "enc:v1:"


def _get_key() -> bytes:
    """Load the 32-byte AES key from config.  Raises if not set."""
    from config import settings  # late import to avoid circular deps at module load
    key_str = settings.field_encryption_key
    if not key_str:
        raise ValueError(
            "FIELD_ENCRYPTION_KEY is not set. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    try:
        key = bytes.fromhex(key_str)
    except ValueError:
        key = base64.b64decode(key_str)
    if len(key) != 32:
        raise ValueError("FIELD_ENCRYPTION_KEY must be exactly 32 bytes (64 hex chars).")
    return key


def encrypt_value(plaintext: str) -> str:
    """Encrypt *plaintext* and return the prefixed, base64-encoded ciphertext."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if not plaintext:
        return plaintext
    key = _get_key()
    nonce = os.urandom(12)
    ciphertext_and_tag = AESGCM(key).encrypt(nonce, plaintext.encode(), None)
    encoded = base64.b64encode(nonce + ciphertext_and_tag).decode()
    return _PREFIX + encoded


def decrypt_value(value: str) -> str:
    """Decrypt a value produced by encrypt_value().

    If *value* does not start with the prefix (i.e. it is legacy plaintext),
    it is returned unchanged so that existing rows can be read before migration.
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if not value or not value.startswith(_PREFIX):
        return value
    key = _get_key()
    raw = base64.b64decode(value[len(_PREFIX):])
    nonce, ciphertext_and_tag = raw[:12], raw[12:]
    return AESGCM(key).decrypt(nonce, ciphertext_and_tag, None).decode()


def hmac_lookup(value: str) -> Optional[str]:
    """Return a deterministic HMAC-SHA256 hex digest suitable for equality lookups.

    Uses the same key as encryption so a single env var covers both operations.
    Returns None for empty/None input.
    """
    if not value:
        return None
    key = _get_key()
    return _hmac.new(key, value.encode(), hashlib.sha256).hexdigest()


class EncryptedString(types.TypeDecorator):
    """SQLAlchemy column type that transparently encrypts on write and decrypts on read.

    Usage in a model::

        from database.encryption import EncryptedString

        class UserProfile(Base):
            hevy_api_key = Column(EncryptedString, nullable=True)
    """
    impl = types.Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Called when writing to the DB — encrypt the value."""
        if value is None:
            return None
        # Don't double-encrypt values that are already encrypted.
        if isinstance(value, str) and value.startswith(_PREFIX):
            return value
        return encrypt_value(value)

    def process_result_value(self, value, dialect):
        """Called when reading from the DB — decrypt the value."""
        if value is None:
            return None
        return decrypt_value(value)
