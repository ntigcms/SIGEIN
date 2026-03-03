"""
Migração: adiciona colunas lido_at e atribuido_to_id na tabela processos.
Execute uma vez: python migrate_processos_lido_atribuido.py
"""
from database import engine
from sqlalchemy import text


def coluna_existe(conn, tabela: str, coluna: str) -> bool:
    r = conn.execute(
        text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = :tabela AND column_name = :coluna
    """),
        {"tabela": tabela, "coluna": coluna},
    )
    return r.fetchone() is not None


def main():
    with engine.begin() as conn:
        if not coluna_existe(conn, "processos", "lido_at"):
            conn.execute(text("ALTER TABLE processos ADD COLUMN lido_at TIMESTAMP"))
            print("Coluna processos.lido_at adicionada.")
        else:
            print("Coluna processos.lido_at já existe.")

        if not coluna_existe(conn, "processos", "atribuido_to_id"):
            conn.execute(
                text("ALTER TABLE processos ADD COLUMN atribuido_to_id INTEGER REFERENCES users(id)")
            )
            print("Coluna processos.atribuido_to_id adicionada.")
        else:
            print("Coluna processos.atribuido_to_id já existe.")
    print("Migração concluída.")


if __name__ == "__main__":
    main()
