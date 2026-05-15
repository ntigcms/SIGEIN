#!/usr/bin/env python3
"""
Script de carga: importa planilha CSV (colunas codigo e descricao) para a tabela produtos_segem.

Uso:
    python carga_produtos_segem.py planilha.csv

O CSV deve ter:
    - Primeira linha: cabeçalho com "codigo" e "descricao" (ou codigo;descricao)
    - Separador: vírgula (,) ou ponto e vírgula (;)
    - Encoding: UTF-8 (ou use --encoding para outro)

Se o código já existir, a descrição é atualizada.
"""

import csv
import sys
import os

# Adiciona o diretório do projeto ao path para importar database e models
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from models import ProdutoSegem


def detect_delimiter(sample_line: str) -> str:
    """Detecta se o CSV usa ',' ou ';'."""
    if ";" in sample_line and sample_line.count(";") >= sample_line.count(","):
        return ";"
    return ","


def normalizar_header(campo: str) -> str:
    """Retorna nome do campo normalizado (minúsculo, sem BOM)."""
    if not campo:
        return ""
    s = campo.strip().lower()
    if s.startswith("\ufeff"):
        s = s[1:]
    return s


def main():
    if len(sys.argv) < 2:
        print("Uso: python carga_produtos_segem.py <arquivo.csv> [--encoding ENCODING]")
        print("Exemplo: python carga_produtos_segem.py planilha.csv")
        print("         python carga_produtos_segem.py planilha.csv --encoding latin-1")
        sys.exit(1)

    path = sys.argv[1]
    encoding = "utf-8"
    if "--encoding" in sys.argv:
        idx = sys.argv.index("--encoding")
        if idx + 1 < len(sys.argv):
            encoding = sys.argv[idx + 1]

    if not os.path.isfile(path):
        print(f"Arquivo não encontrado: {path}")
        sys.exit(1)

    db = SessionLocal()
    try:
        with open(path, "r", encoding=encoding, newline="") as f:
            # Ler primeira linha para detectar delimitador e cabeçalho
            first = f.readline()
            delim = detect_delimiter(first)
            f.seek(0)
            reader = csv.reader(f, delimiter=delim)
            rows = list(reader)

        if not rows:
            print("Arquivo vazio.")
            sys.exit(0)

        headers = [normalizar_header(h) for h in rows[0]]
        idx_codigo = idx_descricao = None
        for i, h in enumerate(headers):
            if h in ("codigo", "código", "cod"):
                idx_codigo = i
            if h in ("descricao", "descrição", "desc"):
                idx_descricao = i

        if idx_codigo is None:
            idx_codigo = 0
        if idx_descricao is None:
            idx_descricao = 1 if len(headers) > 1 else 0

        inseridos = 0
        atualizados = 0
        erros = 0

        for i, row in enumerate(rows[1:], start=2):  # linha 2 em diante
            if len(row) <= max(idx_codigo, idx_descricao):
                continue
            codigo = (row[idx_codigo] or "").strip()
            descricao = (row[idx_descricao] or "").strip()
            if not codigo:
                continue
            try:
                existente = db.query(ProdutoSegem).filter(ProdutoSegem.codigo == codigo).first()
                if existente:
                    existente.descricao = descricao or None
                    atualizados += 1
                else:
                    db.add(ProdutoSegem(codigo=codigo, descricao=descricao or None))
                    inseridos += 1
            except Exception as e:
                erros += 1
                print(f"Linha {i}: erro - {e}")

        db.commit()
        print(f"Carga concluída: {inseridos} inseridos, {atualizados} atualizados.", end="")
        if erros:
            print(f" {erros} erros.")
        else:
            print()

    except Exception as e:
        db.rollback()
        print(f"Erro: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
