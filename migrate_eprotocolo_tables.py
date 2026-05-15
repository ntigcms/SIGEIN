"""
Migração: adiciona colunas faltantes na tabela processos e cria tabela requerentes.
Execute: python migrate_eprotocolo_tables.py
"""
from database import Base, engine
from sqlalchemy import text
import models  # noqa: F401 - registra Requerente em Base.metadata

# Colunas que o modelo Processo espera (com DEFAULT para tabelas com dados existentes)
COLUNAS_PROCESSOS = [
    ("municipio_origem_id", "INTEGER REFERENCES municipios(id)"),
    ("orgao_origem_id", "INTEGER REFERENCES orgaos(id)"),
    ("unidade_origem_id", "INTEGER REFERENCES unidades(id)"),
    ("municipio_atual_id", "INTEGER REFERENCES municipios(id)"),
    ("orgao_atual_id", "INTEGER REFERENCES orgaos(id)"),
    ("unidade_atual_id", "INTEGER REFERENCES unidades(id)"),
    ("status", "VARCHAR(50) DEFAULT 'Em tramitação'"),
    ("urgente", "BOOLEAN DEFAULT FALSE"),
    ("nivel_acesso", "VARCHAR(20) DEFAULT 'Público'"),
    ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ("created_by", "INTEGER REFERENCES users(id)"),
]


def coluna_existe(conn, tabela: str, coluna: str) -> bool:
    r = conn.execute(text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = :tabela AND column_name = :coluna
    """), {"tabela": tabela, "coluna": coluna})
    return r.fetchone() is not None


def tabela_existe(conn, tabela: str) -> bool:
    r = conn.execute(text("""
        SELECT 1 FROM information_schema.tables
        WHERE table_name = :tabela
    """), {"tabela": tabela})
    return r.fetchone() is not None


def main():
    with engine.begin() as conn:
        if not tabela_existe(conn, "processos"):
            print("Tabela processos não existe. Execute: python create_tables.py")
            return
        for col, tipo in COLUNAS_PROCESSOS:
            if coluna_existe(conn, "processos", col):
                print(f"  Coluna processos.{col} já existe, pulando.")
            else:
                try:
                    conn.execute(text(f"ALTER TABLE processos ADD COLUMN {col} {tipo}"))
                    print(f"  Adicionada coluna processos.{col}")
                except Exception as e:
                    print(f"  Erro ao adicionar processos.{col}: {e}")
                    raise
    print("Migração processos concluída.")

    # Criar tabela requerentes se não existir
    Base.metadata.create_all(bind=engine)
    print("Migração concluída.")


if __name__ == "__main__":
    main()
