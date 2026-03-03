from database import SessionLocal, engine
import models
from sqlalchemy.exc import IntegrityError

# Cria as tabelas (caso não existam ainda)
models.Base.metadata.create_all(bind=engine)

# Abre a sessão
db = SessionLocal()

# Dados do admin
username = "admin"
email = "admin@sigein.local"
password = "1234"  # ⚠️ Em produção, use hash seguro (ex: bcrypt)
role = "master"
status = "ativo"

try:
    # Verifica se o admin já existe
    existing_user = db.query(models.User).filter(models.User.email == email).first()

    if existing_user:
        print("⚠️ Usuário admin já existe!")
    else:
        admin_user = models.User(
            nome="Administrador SIGEIN",
            cpf="00000000000",
            email=email,
            password=password,
            municipio_id=None,
            orgao_id=None,
            unidade_id=None,
            perfil=role,
            status=status,
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
