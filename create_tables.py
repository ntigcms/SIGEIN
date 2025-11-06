from database import Base, engine
from models import Equipment

# Cuidado: drop_all apaga todas as tabelas existentes!
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

print("Tabelas recriadas com sucesso!")
