"""AES-256 local storage encryption for sensitive payloads."""

import base64
import json
import logging
import os
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

# Key derivation: password is never sent to a server, only used locally
_SALT = b"lakebase-assess-local-encryption-salt-v1"
_ITERATIONS = 480_000  # OWASP recommended minimum


def _derive_key(password: str) -> bytes:
    """Derive a Fernet-compatible key from a password using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=_ITERATIONS,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))
    return key


def generate_key() -> str:
    """Generate a new encryption key."""
    return Fernet.generate_key().decode("utf-8")


def encrypt_file(input_path: str, output_path: str, key: Optional[str] = None) -> str:
    """Encrypt a file with AES-256 (Fernet).

    Args:
        input_path: Path to the plaintext file.
        output_path: Path for the encrypted file.
        key: Optional Fernet key. If None, generates one.

    Returns:
        The Fernet key used for encryption (save this securely).
    """
    if key is None:
        key = Fernet.generate_key().decode("utf-8")

    fernet = Fernet(key.encode() if isinstance(key, str) else key)

    with open(input_path, "rb") as f:
        plaintext = f.read()

    ciphertext = fernet.encrypt(plaintext)

    # Store key alongside encrypted file for local recovery
    key_path = output_path + ".key"
    with open(key_path, "w") as f:
        f.write(key)

    with open(output_path, "wb") as f:
        f.write(ciphertext)

    logger.info("Encrypted %s → %s (key: %s)", input_path, output_path, key_path)
    return key


def decrypt_file(input_path: str, key: str, output_path: str) -> str:
    """Decrypt a Fernet-encrypted file.

    Args:
        input_path: Path to the encrypted file.
        key: The Fernet key used for encryption.
        output_path: Path for the decrypted output.

    Returns:
        Path to the decrypted file.
    """
    fernet = Fernet(key.encode() if isinstance(key, str) else key)

    with open(input_path, "rb") as f:
        ciphertext = f.read()

    plaintext = fernet.decrypt(ciphertext)

    with open(output_path, "wb") as f:
        f.write(plaintext)

    logger.info("Decrypted %s → %s", input_path, output_path)
    return output_path


def encrypt_payload(input_path: str, output_path: str) -> str:
    """Encrypt the assessment payload JSON.

    Convenience wrapper that generates a key and saves it locally.
    """
    return encrypt_file(input_path, output_path)
