"""
app/utils/encryption.py
────────────────────────
AES-256 encryption/decryption for sensitive fields (DB passwords).
Uses Fernet (AES-128-CBC + HMAC-SHA256) from the cryptography library
— simpler and safer than raw AES for this use case.
"""

import base64
import logging
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _derive_key(secret: str) -> bytes:
    """Derive a 32-byte Fernet key from the application secret."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"cs_nl2sql_salt_v1",
        iterations=390_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(secret.encode()))


_fernet = Fernet(_derive_key(settings.app_secret_key))


def encrypt_password(plain_password: str) -> str:
    """Encrypt a plaintext password. Returns a base64-encoded ciphertext string."""
    return _fernet.encrypt(plain_password.encode()).decode()


def decrypt_password(encrypted_password: str) -> str:
    """Decrypt a password encrypted by encrypt_password()."""
    try:
        return _fernet.decrypt(encrypted_password.encode()).decode()
    except InvalidToken as exc:
        logger.error("Password decryption failed — invalid token")
        raise ValueError("Could not decrypt stored password") from exc
