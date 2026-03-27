import base64
import hashlib
from cryptography.fernet import Fernet
from bot.config.settings import BOT_TOKEN


def _get_fernet() -> Fernet:
    key_material = (BOT_TOKEN or "fallback-key-ddxstore").encode()
    key = base64.urlsafe_b64encode(hashlib.sha256(key_material).digest())
    return Fernet(key)


def encrypt_value(plaintext: str) -> str:
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()
