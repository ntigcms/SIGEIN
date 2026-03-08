"""
Migração: adiciona colunas processo_principal_id, arquivado, arquivado_at, arquivado_por_id na tabela processos.
Execute uma vez: python migrate_processos_arquivado.py
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
        if not coluna_existe(conn, "processos", "processo_principal_id"):
            conn.execute(
                text(
                    "ALTER TABLE processos ADD COLUMN processo_principal_id INTEGER REFERENCES processos(id)"
                )
            )
            print("Coluna processos.processo_principal_id adicionada.")
        else:
            print("Coluna processos.processo_principal_id já existe.")

        if not coluna_existe(conn, "processos", "arquivado"):
            conn.execute(text("ALTER TABLE processos ADD COLUMN arquivado BOOLEAN DEFAULT FALSE"))
            print("Coluna processos.arquivado adicionada.")
        else:
            print("Coluna processos.arquivado já existe.")

        if not coluna_existe(conn, "processos", "arquivado_at"):
            conn.execute(text("ALTER TABLE processos ADD COLUMN arquivado_at TIMESTAMP"))
            print("Coluna processos.arquivado_at adicionada.")
        else:
            print("Coluna processos.arquivado_at já existe.")

        if not coluna_existe(conn, "processos", "arquivado_por_id"):
            conn.execute(
                text("ALTER TABLE processos ADD COLUMN arquivado_por_id INTEGER REFERENCES users(id)")
            )
            print("Coluna processos.arquivado_por_id adicionada.")
        else:
            print("Coluna processos.arquivado_por_id já existe.")
    print("Migração concluída.")


if __name__ == "__main__":
    main()
