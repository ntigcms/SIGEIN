from database import SessionLocal, engine
import models
from sqlalchemy.exc import IntegrityError

# Cria as tabelas (caso não existam ainda)
models.Base.metadata.create_all(bind=engine)

# Abre a sessão
db = SessionLocal()

# Dados do admin
username = "admin"
email = "admin@sigen.local"
password = "1234"  # ⚠️ Em produção, use hash seguro (ex: bcrypt)
role = "Administrador"
status = "Ativo"

try:
    # Verifica se o admin já existe
    existing_user = db.query(models.User).filter(models.User.username == username).first()

    if existing_user:
        print("⚠️ Usuário admin já existe!")
    else:
        admin_user = models.User(
            username=username,
            email=email,
            password=password,
            role=role,
            status=status
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        print(f"✅ Usuário admin criado com sucesso (ID: {admin_user.id})!")

except IntegrityError as e:
    db.rollback()
    print(f"❌ Erro de integridade ao criar admin: {e}")

finally:
    db.close()
