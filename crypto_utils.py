import os, json, base64
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet

CONFIG = 'config.json'

def derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=390_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))

def create_master(password: str):
    salt = os.urandom(16)
    key = derive_key(password, salt)
    with open(CONFIG, 'w') as f:
        json.dump({
            'salt': base64.b64encode(salt).decode(),
            'master_hash': base64.b64encode(key).decode()
        }, f)

def verify_master(password: str) -> bytes:
    cfg = json.load(open(CONFIG))
    salt = base64.b64decode(cfg['salt'])
    expected = cfg['master_hash']
    k = derive_key(password, salt)
    if base64.b64encode(k).decode() != expected:
        raise ValueError('Senha mestre incorreta')
    return k

def encrypt_data(key: bytes, data: bytes) -> bytes:
    return Fernet(key).encrypt(data)

def decrypt_data(key: bytes, token: bytes) -> bytes:
    return Fernet(key).decrypt(token)
