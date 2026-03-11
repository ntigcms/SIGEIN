from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, Float, Date, ForeignKey, func, Enum as SQLEnum
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
import enum

# =====================================================
# ENUMS
# =====================================================

class PerfilEnum(enum.Enum):
    MASTER = "master"
    ADMIN_MUNICIPAL = "admin_municipal"
    GESTOR_ESTOQUE = "gestor_estoque"
    GESTOR_PROTOCOLO = "gestor_protocolo"
    GESTOR_GERAL = "gestor_geral"
    GESTOR_SEGEM = "gestor_segem"
    OPERADOR = "operador"


class StatusUsuarioEnum(enum.Enum):
    ATIVO = "ativo"
    INATIVO = "inativo"
    BLOQUEADO = "bloqueado"
    PENDENTE = "pendente"  # aguardando aprovação


# =====================================================
# USER - REFATORADO
# =====================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nome = Column(String(200), nullable=False)  # ✅ nome completo
    cpf = Column(String(11), unique=True, nullable=False, index=True)  # ✅ só números
    email = Column(String(200), nullable=False, unique=True, index=True)
    password = Column(String(255), nullable=False)  # ✅ use bcrypt para hash
    
    # ✅ Hierarquia administrativa
    municipio_id = Column(Integer, ForeignKey("municipios.id"), nullable=False)
    orgao_id = Column(Integer, ForeignKey("orgaos.id"), nullable=False)
    unidade_id = Column(Integer, ForeignKey("unidades.id"), nullable=False)
    
    # ✅ Perfil e Status gravados como string (colunas existentes role/status)
    perfil = Column("role", String(50), nullable=False, default=PerfilEnum.OPERADOR.value)
    status = Column(String(20), nullable=False, default=StatusUsuarioEnum.PENDENTE.value)
    
    # ✅ Auditoria
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))  # quem criou
    ultimo_acesso = Column(DateTime)
    
    # Relacionamentos
    municipio = relationship("Municipio", back_populates="users")
    orgao = relationship("Orgao")
    unidade = relationship("Unidade")
    movements = relationship("Movement", back_populates="user")
    
    def __str__(self):
        return f"{self.nome} ({self.cpf})"
    
    # ✅ Métodos helper para permissões (usam strings)
    def pode_acessar_inventario(self):
        return self.perfil in [
            PerfilEnum.MASTER.value,
            PerfilEnum.ADMIN_MUNICIPAL.value,
            PerfilEnum.GESTOR_ESTOQUE.value,
            PerfilEnum.GESTOR_GERAL.value,
        ]
    
    def pode_acessar_protocolo(self):
        return self.perfil in [
            PerfilEnum.MASTER.value,
            PerfilEnum.ADMIN_MUNICIPAL.value,
            PerfilEnum.GESTOR_PROTOCOLO.value,
            PerfilEnum.GESTOR_GERAL.value,
        ]

    def pode_acessar_segem(self):
        return self.perfil in [
            PerfilEnum.MASTER.value,
            PerfilEnum.GESTOR_SEGEM.value,
        ]
    
    def pode_gerenciar_usuarios(self):
        return self.perfil in [
            PerfilEnum.MASTER.value,
            PerfilEnum.ADMIN_MUNICIPAL.value,
        ]


# =====================================================
# UNIT (LEGADO)
# =====================================================

class Unit(Base):
    __tablename__ = "units"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), unique=True, nullable=False)
    manager = Column(String(100), nullable=False)

    def __str__(self):
        return self.name


# =====================================================
# PRODUCT - ADICIONAR municipio_id
# =====================================================

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    
    # ✅ ISOLAMENTO POR MUNICÍPIO
    municipio_id = Column(Integer, ForeignKey("municipios.id"), nullable=False)
    orgao_id = Column(Integer, ForeignKey("orgaos.id"), nullable=False)  # ✅ rastreamento

    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    type_id = Column(Integer, ForeignKey("equipment_types.id"), nullable=False)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)

    model = Column(String)
    description = Column(Text)
    controla_por_serie = Column(Boolean, default=True)
    ativo = Column(Boolean, default=True)

    quantidade = Column(Integer, default=0)
    quantidade_minima = Column(Integer, default=0)
    
    # ✅ Auditoria
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))

    # RELACIONAMENTOS
    municipio = relationship("Municipio")
    orgao = relationship("Orgao")
    category = relationship("Category", back_populates="products")
    type = relationship("EquipmentType")
    brand = relationship("Brand")
    items = relationship("Item", back_populates="product", cascade="all, delete-orphan")
    stocks = relationship("Stock", back_populates="product", cascade="all, delete-orphan")


# =====================================================
# ITEM (Produto com série = 1 item = 1 unidade física)
# =====================================================

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True)
    
    # ✅ ISOLAMENTO
    municipio_id = Column(Integer, ForeignKey("municipios.id"), nullable=False)
    orgao_id = Column(Integer, ForeignKey("orgaos.id"), nullable=False)
    
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("unidades.id"), nullable=False)

    tombo = Column(Boolean, default=False)
    num_tombo_ou_serie = Column(String, unique=True)

    estado_id = Column(Integer, ForeignKey("equipment_states.id"))
    status = Column(String, default="Disponível")

    data_aquisicao = Column(Date)
    valor_aquisicao = Column(Float)
    garantia_ate = Column(Date)
    observacao = Column(Text)

    municipio = relationship("Municipio")
    orgao = relationship("Orgao")
    product = relationship("Product", back_populates="items")
    estado = relationship("EquipmentState")
    # Usa a tabela 'unidades', mas o atributo continua sendo 'unit'
    unit = relationship("Unidade", back_populates="items")


# =====================================================
# STOCK (Produto sem série)
# =====================================================

class Stock(Base):
    __tablename__ = "stock"

    id = Column(Integer, primary_key=True)
    
    # ✅ ISOLAMENTO
    municipio_id = Column(Integer, ForeignKey("municipios.id"), nullable=False)
    orgao_id = Column(Integer, ForeignKey("orgaos.id"), nullable=False)

    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("unidades.id"), nullable=False)  # ✅ agora é Unidade

    quantidade = Column(Integer, default=0)
    quantidade_minima = Column(Integer, default=0)
    localizacao = Column(String)

    municipio = relationship("Municipio")
    orgao = relationship("Orgao")
    product = relationship("Product", back_populates="stocks")
    # Usa a tabela 'unidades', mas o atributo continua sendo 'unit'
    unit = relationship("Unidade", back_populates="stocks")


# =====================================================
# MOVEMENT
# =====================================================

class Movement(Base):
    __tablename__ = "movements"

    id = Column(Integer, primary_key=True)

    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=True)

    unit_origem_id = Column(Integer, ForeignKey("unidades.id"))
    unit_destino_id = Column(Integer, ForeignKey("unidades.id"))

    quantidade = Column(Integer, default=1)
    tipo = Column(String(30), nullable=False)

    data = Column(DateTime, default=datetime.utcnow)
    observacao = Column(Text)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # RELACIONAMENTOS
    product = relationship("Product")
    item = relationship("Item")
    user = relationship("User", back_populates="movements")

    unit_origem = relationship("Unidade", foreign_keys=[unit_origem_id])
    unit_destino = relationship("Unidade", foreign_keys=[unit_destino_id])


# =====================================================
# LOG
# =====================================================

class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    usuario = Column(String(50))
    acao = Column(String(255))
    ip = Column(String(50))
    data_hora = Column(DateTime(timezone=True), server_default=func.now())


# =====================================================
# EQUIPMENT TYPE
# =====================================================

class EquipmentType(Base):
    __tablename__ = "equipment_types"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), unique=True, nullable=False)

    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    category = relationship("Category", backref="equipment_types")


# =====================================================
# CATEGORY
# =====================================================

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), unique=True, nullable=False)
    descricao = Column(Text)
    ativo = Column(Boolean, default=True)

    products = relationship("Product", back_populates="category")

    def __str__(self):
        return self.nome


# =====================================================
# BRAND
# =====================================================

class Brand(Base):
    __tablename__ = "brands"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, nullable=False)


# =====================================================
# EQUIPMENT STATE
# =====================================================

class EquipmentState(Base):
    __tablename__ = "equipment_states"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, nullable=False)

# =====================================================
# E-PROTOCOLO - CROSS-MUNICIPAL
# =====================================================

class Processo(Base):
    __tablename__ = "processos"
    
    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String(50), unique=True, index=True)
    ano = Column(Integer)
    assunto = Column(String(500))
    requerente = Column(String(200))
    conteudo = Column(Text)
    
    # ✅ Origem (quem criou)
    municipio_origem_id = Column(Integer, ForeignKey("municipios.id"), nullable=False)
    orgao_origem_id = Column(Integer, ForeignKey("orgaos.id"), nullable=False)
    unidade_origem_id = Column(Integer, ForeignKey("unidades.id"), nullable=False)
    
    # ✅ Localização atual (onde está agora)
    municipio_atual_id = Column(Integer, ForeignKey("municipios.id"), nullable=False)
    orgao_atual_id = Column(Integer, ForeignKey("orgaos.id"), nullable=False)
    unidade_atual_id = Column(Integer, ForeignKey("unidades.id"), nullable=False)
    
    # Status: Em tramitação | Recebido | Em edição | Assinado
    status = Column(String(50), default="Em tramitação")
    urgente = Column(Boolean, default=False)
    nivel_acesso = Column(String(20), default="Público")  # Público/Restrito
    
    # Controle de leitura (aba "Lidos" / "Não lidos")
    lido_at = Column(DateTime, nullable=True)
    # Atribuição (aba "Não atribuídos" / "Atribuídos")
    atribuido_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))
    
    # Apensamento: quando preenchido, este processo está apensado ao processo principal
    processo_principal_id = Column(Integer, ForeignKey("processos.id"), nullable=True)
    
    # Arquivamento
    arquivado = Column(Boolean, default=False)
    arquivado_at = Column(DateTime, nullable=True)
    arquivado_por_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relacionamentos
    atribuido_to = relationship("User", foreign_keys=[atribuido_to_id])
    processo_principal = relationship("Processo", remote_side="Processo.id", foreign_keys=[processo_principal_id], back_populates="apensos")
    apensos = relationship("Processo", back_populates="processo_principal", foreign_keys=[processo_principal_id])
    municipio_origem = relationship("Municipio", foreign_keys=[municipio_origem_id])
    municipio_atual = relationship("Municipio", foreign_keys=[municipio_atual_id])
    orgao_origem = relationship("Orgao", foreign_keys=[orgao_origem_id])
    orgao_atual = relationship("Orgao", foreign_keys=[orgao_atual_id])
    unidade_origem = relationship("Unidade", foreign_keys=[unidade_origem_id])
    unidade_atual = relationship("Unidade", foreign_keys=[unidade_atual_id])
    
    tramites = relationship("Tramite", back_populates="processo")
    assinantes = relationship("ProcessoAssinante", back_populates="processo")
    creator = relationship("User", foreign_keys=[created_by])
    arquivado_por = relationship("User", foreign_keys=[arquivado_por_id])


class ProcessoAssinante(Base):
    """Assinantes do processo (usuários que devem assinar)"""
    __tablename__ = "processo_assinantes"

    id = Column(Integer, primary_key=True, index=True)
    processo_id = Column(Integer, ForeignKey("processos.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    processo = relationship("Processo", back_populates="assinantes")
    user = relationship("User")


class Tramite(Base):
    """Histórico de movimentação do processo"""
    __tablename__ = "tramites"
    
    id = Column(Integer, primary_key=True, index=True)
    processo_id = Column(Integer, ForeignKey("processos.id"), nullable=False)
    
    # De onde saiu
    municipio_origem_id = Column(Integer, ForeignKey("municipios.id"))
    orgao_origem_id = Column(Integer, ForeignKey("orgaos.id"))
    unidade_origem_id = Column(Integer, ForeignKey("unidades.id"))
    
    # Para onde foi
    municipio_destino_id = Column(Integer, ForeignKey("municipios.id"), nullable=False)
    orgao_destino_id = Column(Integer, ForeignKey("orgaos.id"), nullable=False)
    unidade_destino_id = Column(Integer, ForeignKey("unidades.id"), nullable=False)
    
    despacho = Column(Text)
    anexo_path = Column(String(500))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))
    
    processo = relationship("Processo", back_populates="tramites")
    usuario = relationship("User")
    orgao_origem = relationship("Orgao", foreign_keys=[orgao_origem_id])
    unidade_origem = relationship("Unidade", foreign_keys=[unidade_origem_id])
    orgao_destino = relationship("Orgao", foreign_keys=[orgao_destino_id])
    unidade_destino = relationship("Unidade", foreign_keys=[unidade_destino_id])


class Circular(Base):
    __tablename__ = "circulares"
    
    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String(50), unique=True)
    assunto = Column(String(500))
    conteudo = Column(Text)
    
    # Remetente
    municipio_remetente_id = Column(Integer, ForeignKey("municipios.id"), nullable=False)
    orgao_remetente_id = Column(Integer, ForeignKey("orgaos.id"), nullable=False)
    unidade_remetente_id = Column(Integer, ForeignKey("unidades.id"), nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))
    
    destinatarios = relationship("CircularDestinatario", back_populates="circular")


class CircularDestinatario(Base):
    """Destinatários de uma circular (múltiplos)"""
    __tablename__ = "circular_destinatarios"
    
    id = Column(Integer, primary_key=True, index=True)
    circular_id = Column(Integer, ForeignKey("circulares.id"), nullable=False)
    
    municipio_id = Column(Integer, ForeignKey("municipios.id"), nullable=False)
    orgao_id = Column(Integer, ForeignKey("orgaos.id"), nullable=False)
    unidade_id = Column(Integer, ForeignKey("unidades.id"), nullable=False)
    
    recebido = Column(Boolean, default=False)
    data_recebimento = Column(DateTime)
    arquivado = Column(Boolean, default=False)
    
    circular = relationship("Circular", back_populates="destinatarios")


class Requerente(Base):
    """Requerentes para processos do E-Protocolo"""
    __tablename__ = "requerentes"
    
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(200), nullable=False)
    tipo_documento = Column(String(20), nullable=False)  # CPF, CNPJ, RG
    numero_documento = Column(String(20), nullable=False)
    email = Column(String(200))
    cep = Column(String(10), nullable=False)
    endereco = Column(String(300), nullable=False)
    numero_endereco = Column(String(20), nullable=False)
    bairro = Column(String(100), nullable=False)
    complemento = Column(String(100))
    cidade = Column(String(200), nullable=False)
    uf = Column(String(2), nullable=False)
    telefone1 = Column(String(20))
    telefone2 = Column(String(20))
    
    created_at = Column(DateTime, default=datetime.utcnow)


# =====================================================
# CATEGORIA (GRUPO > ASSUNTO > SUBASSUNTO)
# =====================================================

class Grupo(Base):
    """Grupo de categorização (nível superior)"""
    __tablename__ = "grupos"
    
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(200), nullable=False)
    ativo = Column(Boolean, default=True)
    
    assuntos = relationship("Assunto", back_populates="grupo")


class Assunto(Base):
    """Assunto vinculado a um Grupo"""
    __tablename__ = "assuntos"
    
    id = Column(Integer, primary_key=True, index=True)
    grupo_id = Column(Integer, ForeignKey("grupos.id"), nullable=False)
    nome = Column(String(200), nullable=False)
    ativo = Column(Boolean, default=True)
    
    grupo = relationship("Grupo", back_populates="assuntos")
    subassuntos = relationship("Subassunto", back_populates="assunto")


class Subassunto(Base):
    """Subassunto vinculado a um Assunto"""
    __tablename__ = "subassuntos"
    
    id = Column(Integer, primary_key=True, index=True)
    assunto_id = Column(Integer, ForeignKey("assuntos.id"), nullable=False)
    nome = Column(String(200), nullable=False)
    ativo = Column(Boolean, default=True)
    
    assunto = relationship("Assunto", back_populates="subassuntos")


# =====================================================
# HIERARQUIA GEOGRÁFICA/ADMINISTRATIVA
# =====================================================

class Estado(Base):
    __tablename__ = "estados"
    
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), unique=True, nullable=False)
    uf = Column(String(2), unique=True, nullable=False)
    
    municipios = relationship("Municipio", back_populates="estado")


class Municipio(Base):
    __tablename__ = "municipios"
    
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(200), nullable=False)
    codigo_ibge = Column(String(7), unique=True)  # ✅ código IBGE para validação
    estado_id = Column(Integer, ForeignKey("estados.id"), nullable=False)
    ativo = Column(Boolean, default=True)
    
    estado = relationship("Estado", back_populates="municipios")
    orgaos = relationship("Orgao", back_populates="municipio")
    users = relationship("User", back_populates="municipio")


class Orgao(Base):
    """Secretarias/Órgãos dentro de um município"""
    __tablename__ = "orgaos"
    
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(200), nullable=False)  # Ex: "Secretaria de Saúde"
    sigla = Column(String(20))  # Ex: "SESAU"
    municipio_id = Column(Integer, ForeignKey("municipios.id"), nullable=False)
    responsavel = Column(String(200))  # ✅ nome do responsável
    email = Column(String(200))  # ✅ email institucional
    telefone = Column(String(20))
    ativo = Column(Boolean, default=True)
    
    municipio = relationship("Municipio", back_populates="orgaos")
    unidades = relationship("Unidade", back_populates="orgao")


class Unidade(Base):
    __tablename__ = "unidades"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(200), nullable=False)
    sigla = Column(String(20))
    orgao_id = Column(Integer, ForeignKey("orgaos.id"), nullable=False)
    responsavel = Column(String(200))
    ramal = Column(String(10))
    ativo = Column(Boolean, default=True)

    orgao = relationship("Orgao", back_populates="unidades")

    # 🔥 Relacionamentos importantes
    users = relationship("User", back_populates="unidade")
    items = relationship("Item", back_populates="unit")
    stocks = relationship("Stock", back_populates="unit")
    movimentos_origem = relationship(
        "Movement",
        foreign_keys="Movement.unit_origem_id"
    )
    movimentos_destino = relationship(
        "Movement",
        foreign_keys="Movement.unit_destino_id"
    )


# =====================================================
# SEGEM (Sistema de Gestão de Materiais)
# =====================================================

class SegemItem(Base):
    __tablename__ = "segem_itens"

    id = Column(Integer, primary_key=True, index=True)
    municipio_id = Column(Integer, ForeignKey("municipios.id"), nullable=False)
    orgao_id = Column(Integer, ForeignKey("orgaos.id"), nullable=False)

    ano = Column(Integer)  # ANO
    num_tombo_gcm = Column(String(50))  # Nº TOMBO (GCM)
    local = Column(String(200))  # LOCAL
    codigo = Column(String(100))  # CÓDIGO
    descricao = Column(Text)  # DESCRIÇÃO
    situacao = Column(String(100))  # SITUAÇÃO
    valor_rs = Column(Float)  # VALOR R$
    entrada_no_siga = Column(String(100))  # ENTRADA NO SIGA
    nota_de_empenho = Column(String(100))  # NOTA DE EMPENHO
    valor_nota_empenho = Column(Float)  # VALOR DA NOTA DE EMPENHO
    num_nota_fiscal = Column(String(100))  # N° NOTA FISCAL
    nome_empresa = Column(String(200))  # NOME DA EMPRESA
    classificacao_asi = Column(String(100))  # CLASSIFICAÇÃO ASI

    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))

    municipio = relationship("Municipio")
    orgao = relationship("Orgao")
    produtos = relationship("SegemItemProduto", back_populates="segem_item", cascade="all, delete-orphan")


class SegemItemProduto(Base):
    """Produtos adicionais do registro SEGEM (Nº Tombo + Valor), linha do bloco Produto."""
    __tablename__ = "segem_itens_produtos"

    id = Column(Integer, primary_key=True, index=True)
    segem_item_id = Column(Integer, ForeignKey("segem_itens.id"), nullable=False)
    num_tombo_gcm = Column(String(50))
    valor_rs = Column(Float)

    segem_item = relationship("SegemItem", back_populates="produtos")


class ProdutoSegem(Base):
    """Catálogo de produtos SEGEM (código + descrição) para preenchimento automático no formulário."""
    __tablename__ = "produtos_segem"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(100), unique=True, nullable=False, index=True)
    descricao = Column(Text)
