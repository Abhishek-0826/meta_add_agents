"""
Encrypt/decrypt client Meta access tokens at rest (design doc §12 Security table).
Never log a decrypted token. Never return one from the API.
"""
from cryptography.fernet import Fernet

from app.config import get_settings

settings = get_settings()


def _fernet() -> Fernet:
    if not settings.FERNET_KEY:
        raise RuntimeError(
            "FERNET_KEY is not set. Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\" "
            "and put it in .env"
        )
    return Fernet(settings.FERNET_KEY.encode())


def encrypt_token(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()
