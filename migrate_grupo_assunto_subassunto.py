"""
Migração: cria tabelas grupos, assuntos e subassuntos.
Execute: python migrate_grupo_assunto_subassunto.py
"""
from database import Base, engine
import models  # noqa: F401 - registra Grupo, Assunto, Subassunto em Base.metadata


def main():
    Base.metadata.create_all(bind=engine, tables=[
        Base.metadata.tables["grupos"],
        Base.metadata.tables["assuntos"],
        Base.metadata.tables["subassuntos"],
    ])
    print("Migração grupos/assuntos/subassuntos concluída.")


if __name__ == "__main__":
    main()
