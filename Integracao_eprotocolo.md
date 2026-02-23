# INTEGRAÇÃO DO E-PROTOCOLO NO SISTEMA EXISTENTE

## 📁 Estrutura de Arquivos

Crie a seguinte estrutura de pastas:

```
routers/
  └── eprotocolo.py  # Router criado (eprotocolo_router.py)

templates/
  └── eprotocolo/
      ├── dashboard.html  # Dashboard criado (eprotocolo_dashboard.html)
      ├── processos/
      │   ├── criar.html
      │   ├── caixa.html
      │   ├── consulta.html
      │   ├── historico.html
      │   ├── arquivados.html
      │   └── atribuir.html
      ├── circulares/
      │   ├── criar.html
      │   ├── caixa.html
      │   ├── historico.html
      │   └── arquivados.html
      └── ajuda/
          ├── manual.html
          ├── novidades.html
          ├── faq.html
          ├── termo_uso.html
          └── integracao.html
```

## 🔧 Passo 1: Adicionar o Router no main.py

No arquivo principal da aplicação (provavelmente `main.py` ou `app.py`):

```python
from routers import eprotocolo  # ← adicione este import

# ... resto dos imports

app = FastAPI()

# ... outros routers
app.include_router(eprotocolo.router)  # ← adicione esta linha
```

## 🎨 Passo 2: Adicionar Botão no Menu Lateral

No template `base.html` (ou onde está o menu lateral), adicione:

```html
<!-- Menu Lateral -->
<nav class="sidebar">
    <!-- ... outros itens do menu ... -->
    
    <!-- ✅ ADICIONE ESTE ITEM -->
    <a href="/eprotocolo" class="menu-item">
        <i class="fas fa-file-signature"></i>
        <span>E-Protocolo</span>
    </a>
    
    <!-- ... resto do menu ... -->
</nav>
```

## 📝 Passo 3: Criar Templates Placeholder

Para cada rota funcionar, crie templates básicos. Exemplo de template genérico:

**templates/eprotocolo/processos/criar.html**
```html
{% extends "base.html" %}
{% block title %}Criar Processo - E-Protocolo{% endblock %}

{% block content %}
<div class="container">
    <h2>Criar Processo</h2>
    <p>Em desenvolvimento...</p>
    <a href="/eprotocolo" class="btn-back">← Voltar ao Dashboard</a>
</div>
{% endblock %}
```

Repita para todas as páginas listadas na estrutura acima.

## 🗄️ Passo 4: Modelos de Banco (Opcional)

Se precisar criar tabelas no banco, adicione em `models.py`:

```python
class Processo(Base):
    __tablename__ = "processos"
    
    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String, unique=True, index=True)
    ano = Column(Integer)
    assunto = Column(String)
    requerente = Column(String)
    conteudo = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    # ... outros campos

class Circular(Base):
    __tablename__ = "circulares"
    
    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String, unique=True)
    assunto = Column(String)
    conteudo = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    # ... outros campos
```

## 🎯 Passo 5: CSS Global (Opcional)

Adicione no `base.html` ou em arquivo CSS separado:

```css
/* Ícone do menu E-Protocolo */
.menu-item i.fa-file-signature {
    color: #0d6efd;
}

.menu-item:hover i.fa-file-signature {
    color: #fff;
}
```

## ✅ Checklist de Integração

- [ ] Copiar `eprotocolo_router.py` → `routers/eprotocolo.py`
- [ ] Copiar `eprotocolo_dashboard.html` → `templates/eprotocolo/dashboard.html`
- [ ] Adicionar `app.include_router(eprotocolo.router)` no main.py
- [ ] Adicionar botão "E-Protocolo" no menu lateral do base.html
- [ ] Criar pastas: `templates/eprotocolo/processos/`, `circulares/`, `ajuda/`
- [ ] Criar templates placeholder para cada rota
- [ ] (Opcional) Adicionar modelos no banco de dados
- [ ] Testar acesso em http://localhost:8000/eprotocolo

## 🚀 Próximos Passos

Após a integração básica funcionar:

1. Implementar formulário de "Criar Processo" com editor rico
2. Implementar "Caixa de Processos" com DataTables e filtros
3. Adicionar sistema de anexos (upload de PDFs)
4. Implementar tramitação de processos
5. Sistema de assinaturas digitais
6. Notificações em tempo real

---

**IMPORTANTE:** Os arquivos criados são:
- `eprotocolo_router.py` (renomeie para `routers/eprotocolo.py`)
- `eprotocolo_dashboard.html` (mova para `templates/eprotocolo/dashboard.html`)