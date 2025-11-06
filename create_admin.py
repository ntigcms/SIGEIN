from database import SessionLocal, engine
import models

# Criar tabelas (caso ainda não existam)
models.Base.metadata.create_all(bind=engine)

# Abrir sessão
db = SessionLocal()

# Dados do admin
username = "admin"
password = "admin123"  # ⚠️ em produção, use hash!

# Verifica se já existe
existing_user = db.query(models.User).filter(models.User.username == username).first()
if existing_user:
    print("Usuário admin já existe!")
else:
    admin_user = models.User(username=username, password=password)
    db.add(admin_user)
    db.commit()
    print("Usuário admin criado com sucesso!")

db.close()
