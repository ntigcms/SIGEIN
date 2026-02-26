# init_db.py
from database import Base, engine, SessionLocal
import models

# ======== Criar todas as tabelas ========
print("Criando o banco e tabelas...")
Base.metadata.drop_all(bind=engine)  # remove tabelas antigas (opcional)
Base.metadata.create_all(bind=engine)
print("Tabelas criadas com sucesso!")

# ======== Inserir dados de teste ========
db = SessionLocal()

# Exemplo: criar alguns equipamentos
equipments = [
    models.Equipment(type="Computador", brand="Dell", status="Ativo", state="Novo", location="Sala 1"),
    models.Equipment(type="Impressora", brand="HP", status="Manutenção", state="Usado", location="Sala 2"),
    models.Equipment(type="Scanner", brand="Canon", status="Ativo", state="Novo", location="Recepção"),
]

for eq in equipments:
    db.add(eq)

# Exemplo antigo de usuário administrador (mantido apenas como comentário)
# admin_user = models.User(username="admin", password="1234")
# db.add(admin_user)

db.commit()
db.close()
print("Dados iniciais inseridos com sucesso!")
