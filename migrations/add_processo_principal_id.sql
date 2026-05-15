-- Migração: Adicionar coluna processo_principal_id para apensamento de processos
-- Execute este script no banco de dados se a coluna ainda não existir.
-- PostgreSQL:
ALTER TABLE processos ADD COLUMN IF NOT EXISTS processo_principal_id INTEGER REFERENCES processos(id);
