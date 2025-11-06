# 🧭 SIGEN — Sistema Integrado de Gestão de Estoque e Inventário

![SIGEN](https://img.shields.io/badge/SIGEN-v1.0-0d6efd)
![FastAPI](https://img.shields.io/badge/FastAPI-✨-00a7c4)
![Jinja2](https://img.shields.io/badge/Jinja2-Templates-ff5b5b)
![SQLite](https://img.shields.io/badge/SQLite-DB-003b57)

Aplicação web em FastAPI + Jinja2 para gerenciar equipamentos, unidades, usuários, movimentações e logs.

---

## 🎯 Visão geral
- Backend: FastAPI  
- Templates: Jinja2  
- Banco de dados: SQLite (sigen.db)  
- Exportações: PDF (ReportLab) e XLSX (openpyxl)

## 🎨 Paleta de cores (interface)
| Cor | Variável | Hex |
|---:|:---:|:---:|
| 🟦 Azul Primário | --color-primary | #0d6efd |
| 🟩 Verde | --color-success | #198754 |
| 🟨 Amarelo | --color-warning | #ffc107 |
| 🟥 Vermelho | --color-danger | #dc3545 |
| ⬜ Fundo | --color-bg | #ffffff |
| ⚫ Texto | --color-text | #222222 |

---

## 📁 Estrutura principal do projeto
| Arquivo / Pasta | Descrição |
|---|---|
| main.py | Ponto de entrada da aplicação |
| requirements.txt | Dependências do projeto |
| database.py | Configuração do SQLAlchemy / engine / get_db |
| dependencies.py | Sessões em memória e helpers (registrar_log, get_current_user) |
| models.py | Modelos ORM (User, Unit, Equipment, Movement, Log) |
| routers/ | Rotas organizadas por domínio (auth, dashboard, equipment, users, logs) |
| templates/ | Templates Jinja2 (views) |
| static/style.css | Estilos principais |
| init_db.py | Cria tabelas + seed |
| create_admin.py | Cria usuário administrador |
| create_tables.py | Recria tabelas (apaga dados) |
| auth.py | Helpers de hash (passlib) — integrar ao fluxo de persistência de senhas |

---

## 🚀 Rotas principais
| Método | Caminho | Descrição |
|---:|:---|:---|
| GET | /login | Formulário de login |
| POST | /login | Autenticar usuário |
| GET | /dashboard | Painel principal |
| GET | /equipment | Listagem de equipamentos |
| GET / POST | /equipment/add | Adicionar equipamento |
| GET / POST | /equipment/edit/{id} | Editar equipamento |
| GET / POST | /equipment/confirm_delete/{id} | Confirmar / excluir equipamento |
| GET /users | CRUD de usuários |
| GET | /logs | Listar logs |
| GET | /logs/export/pdf | Exportar logs em PDF |
| GET | /logs/export/xlsx | Exportar logs em XLSX |

(Ver arquivos em `routers/` para detalhes de implementação.)

---

## ⚙️ Instalação (ambiente local)
1. Criar e ativar virtualenv:
```powershell
python -m venv .venv
# PowerShell (Windows)
.\.venv\Scripts\Activate.ps1
# CMD (Windows)
.\.venv\Scripts\activate.bat
# macOS / Linux
source .venv/bin/activate


2. Instalar dependências
pip install -r requirements.txt

3. Preparar banco de dados

# O projeto usa SQLite (sigen.db) definido em database.py.

3. Criar tabelas e dados iniciais:

python init_db.py


4. Criar apenas o admin:

python create_admin.py

5. Executar a aplicação:

uvicorn main:app --host 0.0.0.0 --port 8000 --reload

6. Acessar a aplicação:

Acesse em: http://127.0.0.1:8000
```
🚀 Rotas Principais
| Caminho                          | Descrição                  |
| -------------------------------- | -------------------------- |
| `/login`                         | Formulário de login        |
| `/dashboard`                     | Painel principal           |
| `/equipment`                     | Listagem de equipamentos   |
| `/equipment/add`                 | Adicionar novo equipamento |
| `/equipment/edit/{id}`           | Editar equipamento         |
| `/equipment/confirm_delete/{id}` | Confirmar exclusão         |
| `/users`                         | Gerenciar usuários         |
| `/logs`                          | Listar logs                |
| `/logs/export/pdf`               | Exportar logs em PDF       |
| `/logs/export/xlsx`              | Exportar logs em Excel     |

🧩 Observações e Melhorias Sugeridas

⚠️ Senhas: atualmente armazenadas em texto. Utilize hashing (funções em auth.py).

🧠 Sessões: armazenadas em dicionário em memória (dependencies.py).
Use Redis ou DB para produção.

🧾 Nomes inconsistentes entre templates e modelos (routers/equipment.py) — revisar para unificação.

📦 Exportações de logs usam bibliotecas diferentes (ReportLab, openpyxl) — verificar versões.

🌍 Idioma: todas as rotas e templates estão em português — ajustar conforme público-alvo.

🤝 Contribuição / Desenvolvimento

1. Crie uma nova branch

2. Faça as alterações

3. Teste localmente acessando as rotas

4. Para recriar tabelas (⚠️ apaga dados):

python create_tables.py

📜 Licença

Projeto sem licença especificada.
Adicione um arquivo LICENSE conforme necessário.

📬 Contato

Abra uma issue ou pull request neste repositório para sugestões, correções ou dúvidas.
