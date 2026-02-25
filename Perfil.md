✅ MASTER
- Acesso total ao sistema
- Gerencia múltiplos municípios
- Acessa configurações globais
- Único que pode criar/editar usuários MASTER

✅ ADMIN_MUNICIPAL (era "Admin")
- Acesso total ao município lotado
- Pode criar/editar todos os usuários (exceto MASTER) do seu município
- Acessa inventário + protocolo completo
- Pode gerenciar órgãos/unidades

✅ GESTOR_ESTOQUE (era "Estoque")
- Acesso total ao inventário do seu órgão
- Visualiza estoque de outras unidades do mesmo órgão
- Gera relatórios
- NÃO acessa protocolo
- NÃO gerencia usuários

✅ GESTOR_PROTOCOLO (era "Servidor")
- Acesso total ao protocolo do seu órgão/unidade
- Pode criar/tramitar processos e circulares
- Visualiza histórico completo
- NÃO acessa inventário
- NÃO gerencia usuários

✅ GESTOR_GERAL (era "Lider")
- Combina GESTOR_ESTOQUE + GESTOR_PROTOCOLO
- Visão 360° do órgão
- NÃO gerencia usuários

⚠️ SUGESTÃO ADICIONAL - OPERADOR
- Acesso básico (consulta + ações limitadas)
- Pode receber/visualizar processos
- Pode dar baixa em estoque
- NÃO pode criar/editar/excluir nada