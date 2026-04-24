# SIGEIN — Sistema Integrado de Gestão de Estoque e Inventário

![FastAPI](https://img.shields.io/badge/FastAPI-✨-00a7c4)
![Jinja2](https://img.shields.io/badge/Jinja2-Templates-ff5b5b)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-DB-336791)

Aplicação web em **FastAPI** + **Jinja2** para gestão de patrimônio/estoque, movimentações, cadastros, **SEGEM**, **E-Protocolo**, usuários e auditoria (logs).

> **Comercialização:** o produto pode ser apresentado como **SIGEIP**; o repositório mantém o nome técnico **SIGEIN**.

---

## Visão geral

| Camada | Tecnologia |
|--------|------------|
| Backend | FastAPI |
| Templates | Jinja2 |
| Banco de dados | **PostgreSQL** (`psycopg2`) |
| Sessão | `SessionMiddleware` (cookie) |
| Exportações | PDF (ReportLab) e XLSX (openpyxl) |

### Variável de ambiente do banco

A conexão é definida em `database.py` pela variável **`DATABASE_URL`**.

- **Desenvolvimento local (padrão):** `postgresql+psycopg2://postgres:1234@localhost:5432/sigein`
- **Produção (ex.: AWS RDS):** configure `DATABASE_URL` com o endpoint do RDS, usuário, senha e nome do banco — **não commite credenciais no repositório**.

Exemplo:

```text
DATABASE_URL=postgresql+psycopg2://usuario:senha@endpoint-rds.region.rds.amazonaws.com:5432/sigein
```

---

## Pré-requisitos

- Python 3.10+ (recomendado)
- **PostgreSQL** instalado e em execução
- Banco criado (ex.: `sigein`) e usuário com permissão de DDL na primeira carga (`init_db.py`)

---

## Estrutura principal do projeto

| Arquivo / Pasta | Descrição |
|-----------------|-----------|
| `main.py` | Ponto de entrada FastAPI, middleware de sessão, inclusão dos routers |
| `database.py` | Engine SQLAlchemy, `DATABASE_URL`, `get_db` |
| `models.py` | Modelos ORM |
| `dependencies.py` | `get_current_user`, `registrar_log` |
| `security.py` | Hash/verificação de senha (bcrypt) |
| `routers/` | Rotas por domínio (auth, dashboard, users, products, stock, movements, segem, eprotocolo, logs, etc.) |
| `templates/` | Views Jinja2 |
| `static/` | CSS, JS e assets |
| `init_db.py` | Cria tabelas e dados iniciais |
| `create_admin.py` | Cria usuário administrador |
| `create_tables.py` | Recria tabelas (**apaga dados**) |
| `Rodar-SIGEIN.ps1` | Script auxiliar para subir o servidor no Windows |

---

## Instalação (ambiente local)

### 1. Criar e ativar virtualenv

```powershell
python -m venv .venv
# PowerShell (Windows)
.\.venv\Scripts\Activate.ps1
```

### 2. Instalar dependências

```powershell
pip install -r requirements.txt
```

### 3. Configurar PostgreSQL

1. Crie o banco `sigein` (ou outro nome e ajuste `DATABASE_URL`).
2. Exporte `DATABASE_URL` se não for usar o padrão de `database.py`:

```powershell
$env:DATABASE_URL = "postgresql+psycopg2://postgres:SUA_SENHA@localhost:5432/sigein"
```

### 4. Criar tabelas e dados iniciais

```powershell
python init_db.py
```

### 5. (Opcional) Criar apenas o admin

```powershell
python create_admin.py
```

### 6. Executar a aplicação

```powershell
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Ou no Windows:

```powershell
.\Rodar-SIGEIN.ps1 -Port 8000
```

Acesse: **http://127.0.0.1:8000**

---

## Rotas e módulos (resumo)

| Prefixo / área | Descrição |
|------------------|-----------|
| `/login`, `/logout` | Autenticação |
| `/dashboard` | Painel |
| `/users` | Usuários |
| `/units`, `/orgaos` | Unidades e órgãos |
| `/products` | Produtos / itens |
| `/stock` | Estoque |
| `/movements` | Movimentações |
| `/equipment`, `/equipment-types`, `/brands`, `/categories`, `/states` | Equipamentos e cadastros auxiliares |
| `/segem` | Módulo SEGEM |
| `/eprotocolo` | Protocolo eletrônico (processos, circulares, administração) |
| `/logs` | Logs e exportação PDF/XLSX |
| `/api/...` | APIs auxiliares (geografia, etc.) |

Detalhes: arquivos em `routers/`.

---

## Produção e AWS (RDS)

- Use uma instância **Amazon RDS for PostgreSQL** na mesma VPC (ou com rota segura) do servidor da aplicação.
- No **Security Group** do RDS, libere a porta **5432** apenas para o security group do EC2/Lightsail (ou IP fixo do app).
- Defina **`DATABASE_URL`** no ambiente do servidor (systemd, Docker, Elastic Beanstalk, etc.).
- Gere **`SECRET_KEY`** forte para `SessionMiddleware` em `main.py` (variável de ambiente recomendada).

Fluxo detalhado de deploy na AWS pode ser documentado em um guia separado (EC2/Lightsail + Nginx + HTTPS).

---

## Observações

- **Senhas:** login usa hash bcrypt (`security.py`); migração automática de hashes antigos no login quando aplicável.
- **Sessões:** cookie assinado via `SessionMiddleware` (não é mais dicionário em memória).
- Para **recriar tabelas** (⚠️ apaga dados): `python create_tables.py`

---

## Licença

Projeto sem licença especificada. Adicione um arquivo `LICENSE` conforme necessário.

---

## Contato

Sugestões e correções: abra uma issue ou pull request no repositório.
