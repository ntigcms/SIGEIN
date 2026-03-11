"""
Migração: Corrige as FKs da tabela movements para referenciar 'unidades' em vez de 'units'.

O erro ocorre porque a tabela movements foi criada com FKs apontando para "units",
mas o sistema usa a tabela "unidades" para unidades administrativas.

Execute: python fix_movements_fk.py
"""
import psycopg2
from database import SQLALCHEMY_DATABASE_URL

# Converte URL SQLAlchemy para conexão psycopg2
url = SQLALCHEMY_DATABASE_URL.replace("postgresql+psycopg2://", "postgresql://")

def main():
    conn = psycopg2.connect(url)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # 1. Remover FKs das colunas unit_origem_id e unit_destino_id
        cur.execute("""
            SELECT c.conname FROM pg_constraint c
            JOIN pg_attribute a ON a.attnum = ANY(c.conkey) AND a.attrelid = c.conrelid
            WHERE c.conrelid = 'movements'::regclass AND c.contype = 'f'
            AND a.attname IN ('unit_origem_id', 'unit_destino_id');
        """)
        for (conname,) in cur.fetchall():
            cur.execute(f'ALTER TABLE movements DROP CONSTRAINT IF EXISTS "{conname}"')
            print(f"  Removida: {conname}")

        # 2. Adicionar novas FKs apontando para unidades (só se não existir)
        cur.execute("""
            SELECT 1 FROM pg_constraint 
            WHERE conrelid = 'movements'::regclass 
            AND conname = 'fk_movements_unit_origem';
        """)
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE movements 
                ADD CONSTRAINT fk_movements_unit_origem 
                FOREIGN KEY (unit_origem_id) REFERENCES unidades(id);
            """)
            print("  Adicionada: fk_movements_unit_origem -> unidades(id)")

        cur.execute("""
            SELECT 1 FROM pg_constraint 
            WHERE conrelid = 'movements'::regclass 
            AND conname = 'fk_movements_unit_destino';
        """)
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE movements 
                ADD CONSTRAINT fk_movements_unit_destino 
                FOREIGN KEY (unit_destino_id) REFERENCES unidades(id);
            """)
            print("  Adicionada: fk_movements_unit_destino -> unidades(id)")

        conn.commit()
        print("\nMigração concluída com sucesso!")

    except Exception as e:
        conn.rollback()
        print(f"\nErro: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
