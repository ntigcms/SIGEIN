from sqlalchemy import text

from database import SessionLocal, engine


def migrate_logs_municipio():
    with engine.begin() as conn:
        # 1) Garante colunas de tenant/auditoria na tabela logs
        conn.execute(
            text(
                """
                ALTER TABLE logs
                ADD COLUMN IF NOT EXISTS municipio_id INTEGER
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE logs
                ADD COLUMN IF NOT EXISTS user_id INTEGER
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE logs
                ADD COLUMN IF NOT EXISTS user_agent VARCHAR(500)
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE logs
                ADD COLUMN IF NOT EXISTS tipo VARCHAR(20) NOT NULL DEFAULT 'operacional'
                """
            )
        )

        # 2) Cria FKs (municipio/user), se ainda não existirem
        fk_exists = conn.execute(
            text(
                """
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'logs_municipio_id_fkey'
                """
            )
        ).scalar()
        if not fk_exists:
            conn.execute(
                text(
                    """
                    ALTER TABLE logs
                    ADD CONSTRAINT logs_municipio_id_fkey
                    FOREIGN KEY (municipio_id) REFERENCES municipios(id)
                    """
                )
            )
        user_fk_exists = conn.execute(
            text(
                """
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'logs_user_id_fkey'
                """
            )
        ).scalar()
        if not user_fk_exists:
            conn.execute(
                text(
                    """
                    ALTER TABLE logs
                    ADD CONSTRAINT logs_user_id_fkey
                    FOREIGN KEY (user_id) REFERENCES users(id)
                    """
                )
            )

        # 3) Índices para consulta por tenant/auditoria
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_logs_municipio_id
                ON logs (municipio_id)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_logs_user_id
                ON logs (user_id)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_logs_tipo
                ON logs (tipo)
                """
            )
        )

        # 4) Backfill: copia municipio/user pelo email gravado no log
        conn.execute(
            text(
                """
                UPDATE logs l
                SET municipio_id = u.municipio_id
                FROM users u
                WHERE l.municipio_id IS NULL
                  AND l.usuario = u.email
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE logs l
                SET user_id = u.id
                FROM users u
                WHERE l.user_id IS NULL
                  AND l.usuario = u.email
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE logs
                SET tipo = CASE
                    WHEN lower(acao) LIKE '%login%' OR lower(acao) LIKE '%logout%'
                        THEN 'seguranca'
                    ELSE 'operacional'
                END
                WHERE tipo IS NULL OR tipo = ''
                """
            )
        )


if __name__ == "__main__":
    migrate_logs_municipio()
    print("Migracao de logs.municipio_id concluida.")
