from database import Base, engine

# Cuidado: drop_all apaga todas as tabelas existentes!
Base.metadata.create_all(bind=engine)

print("Tabelas recriadas com sucesso!")
