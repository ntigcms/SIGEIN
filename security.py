import hashlib
from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Aceita:
    - bcrypt (novo padrão)
    - SHA-256 legado (migração)
    """

    if not hashed_password:
        return False

    # Se já for bcrypt
    if hashed_password.startswith("$2b$"):
        return pwd_context.verify(plain_password, hashed_password)

    # Se for SHA-256 antigo
    sha256_hash = hashlib.sha256(plain_password.encode()).hexdigest()
    return sha256_hash == hashed_password