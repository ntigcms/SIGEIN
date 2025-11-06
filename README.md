# SIGEN — Sistema Integrado de Gestão de Estoque e Inventário

Pequena aplicação web em FastAPI + Jinja2 para gerenciar equipamentos, unidades, usuários, movimentações e logs.

Principais arquivos
- [main.py](main.py) — ponto de entrada da aplicação.
- [requirements.txt](requirements.txt) — dependências.
- [database.py](database.py) — configuração do SQLAlchemy e provider `get_db`.
- [dependencies.py](dependencies.py) — sessão simples em memória e `registrar_log` / `get_current_user`.
  - [`dependencies.get_current_user`](dependencies.py)
  - [`dependencies.registrar_log`](dependencies.py)
- [models.py](models.py) — modelos ORM (User, Unit, Equipment, Movement, Log).
  - [`models.Equipment`](models.py)
  - [`models.User`](models.py)
  - [`models.Log`](models.py)
- Rotas (APIRouters)
  - [`routers.auth.login_post`](routers/auth.py) — login/logout e registro de sessão.
  - [`routers.auth.login_form`](routers/auth.py)
  - [`routers.dashboard.dashboard`](routers/dashboard.py)
  - [`routers.equipment.list_equipment`](routers/equipment.py)
  - [`routers.equipment.add_equipment`](routers/equipment.py)
  - [`routers.equipment.edit_equipment`](routers/equipment.py)
  - [`routers.equipment.confirm_delete_equipment`](routers/equipment.py)
  - [`routers.users.list_users`](routers/users.py)
  - [`routers.users.add_user`](routers/users.py)
  - [`routers.users.edit_user_form`](routers/users.py)
  - [`routers.logs.listar_logs`](routers/logs.py) — listagem e exportação de logs.
  - [`routers.logs.export_logs_pdf`](routers/logs.py)
  - [`routers.logs.export_logs_xlsx`](routers/logs.py)
- Templates principais (Jinja2)
  - [templates/base.html](templates/base.html)
  - [templates/login.html](templates/login.html)
  - [templates/dashboard.html](templates/dashboard.html)
  - [templates/equipment_list.html](templates/equipment_list.html)
  - [templates/equipment_form.html](templates/equipment_form.html)
  - [templates/equipment_confirm_delete.html](templates/equipment_confirm_delete.html)
  - [templates/users_list.html](templates/users_list.html)
  - [templates/user_form.html](templates/user_form.html)
  - [templates/logs_list.html](templates/logs_list.html)
- Arquivos auxiliares
  - [static/style.css](static/style.css)
  - [init_db.py](init_db.py) — script para inicializar o banco (drop/create + seed).
  - [create_admin.py](create_admin.py) — cria usuário admin.
  - [create_tables.py](create_tables.py) — recria tabelas (drop/create).
  - [auth.py](auth.py) — helpers de hash de senha (passlib) — não totalmente integrado ao fluxo atual.

Instalação (local)

1. Criar e ativar venv:
```sh
python -m venv .venv
# Windows
.\venv\Scripts\Activate.ps1
# Unix / macOS
source .venv/bin/activate

2. Instalar dependências:
pip install -r [requirements.txt](http://_vscodecontentref_/0)

Preparar banco de dados

O projeto usa SQLite em sigen.db (definido em database.py).
Para criar as tabelas iniciais e dados de exemplo:

python [init_db.py](http://_vscodecontentref_/1)

Para criar apenas um admin:

python [create_admin.py](http://_vscodecontentref_/2)

Executar a aplicação:

uvicorn main:app --host 0.0.0.0 --port 8000 --reload

A aplicação ficará disponível em http://127.0.0.1:8000

Rotas importantes (exemplos)

/login — formulário de login (routers.auth.login_form)
/dashboard — painel principal (routers.dashboard.dashboard)
/equipment — listagem de equipamentos (routers.equipment.list_equipment)
/equipment/add — adicionar equipamento (form + POST) (routers.equipment.add_equipment)
/equipment/edit/{id} — editar equipamento (routers.equipment.edit_equipment)
/equipment/confirm_delete/{id} — confirmar exclusão (routers.equipment.confirm_delete_equipment)
/users — listagem/cadastro/edição/exclusão de usuários (routers.users.list_users, routers.users.add_user)
/logs — listar logs e exportar:
/logs/export/pdf — exporta PDF (routers.logs.export_logs_pdf)
/logs/export/xlsx — exporta XLSX (routers.logs.export_logs_xlsx)
Observações importantes / melhorias sugeridas

Senhas de usuários são armazenadas em texto em vários pontos (ex.: routers.auth.login_post, routers.users.add_user). Use hashing com as funções em auth.py e nunca salve senhas em texto.
O armazenamento de sessões é um dicionário em memória (sessions em dependencies.py); para produção, use backend persistente (Redis, DB) e tokens seguros.
Algumas inconsistências de nomes entre templates e modelos (por exemplo nome vs name, marca vs brand) estão mapeadas em routers/equipment.py, revisar modelos e formulários para unificar.
Exports de logs usam bibliotecas diferentes (ReportLab e openpyxl) em routers/logs.py. Conferir requisitos/versões se for executar exportação.
Rotas e templates estão escritos em português — ajustar conforme público alvo.
Como contribuir / desenvolvimento

Criar branch, alterar código, rodar testes manuais navegando nas páginas.
Para recriar tabelas (perde dados):

python [create_tables.py](http://_vscodecontentref_/3)

Licença

Projeto sem licença especificada — adicionar LICENSE conforme necessário.
Contato

Abrir issues/PR neste repositório.