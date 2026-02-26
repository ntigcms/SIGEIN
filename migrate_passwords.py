# migrate_passwords.py
from sqlalchemy.orm import Session
from database import SessionLocal
import models
from passlib.context import CryptContext

# Configura PassLib com bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Gera hash seguro usando bcrypt (trunca para 72 bytes se necessário)."""
    truncated = password[:72]  # bcrypt suporta no máximo 72 bytes
    return pwd_context.hash(truncated)

def migrate_passwords():
    db: Session = SessionLocal()
    try:
        users = db.query(models.User).all()
        for user in users:
            print(f"Atualizando senha de {user.email}")
            if not user.password:
                print("⚠️ Sem senha definida, pulando")
                continue
            try:
                hashed = hash_password(user.password)
                user.password = hashed
                db.add(user)
                db.commit()
                print("✅ Senha atualizada com sucesso")
            except Exception as e:
                db.rollback()
                print(f"Erro ao atualizar senha: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    migrate_passwords()