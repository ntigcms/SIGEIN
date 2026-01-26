from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, Float, Date, ForeignKey, func
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(100), nullable=False)
    email = Column(String(120), nullable=False, unique=True)
    password = Column(String(100), nullable=False)
    role = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)
    movements = relationship("Movement", back_populates="user")

    def __repr__(self):
        return f"<User(username='{self.username}')>"

    def __str__(self):
        return self.username


class Unit(Base):
    __tablename__ = "units"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), unique=True, nullable=False)      # Nome da unidade
    manager = Column(String(100), nullable=False)               # Responsável pela unidade

    def __repr__(self):
        return f"<Unit(id={self.id}, name='{self.name}', manager='{self.manager}')>"

    def __str__(self):
        return self.name


class Equipment(Base):
    __tablename__ = "equipments"  # <-- nome da tabela atualizado
    
    id = Column(Integer, primary_key=True, index=True)
    # Tipo do equipamento
    tipo_id = Column(Integer, ForeignKey("equipment_types.id"))
    tipo = relationship("EquipmentType")
    # Marca
    brand_id = Column(Integer, ForeignKey("brands.id"))
    brand = relationship("Brand")
    # Status (ativo/inativo)
    status = Column(String)
    # Estado do equipamento
    state_id = Column(Integer, ForeignKey("equipment_states.id"))
    state = relationship("EquipmentState")
    # Unidade responsável
    unit_id = Column(Integer, ForeignKey("units.id"))
    unit = relationship("Unit")
    # Movimentações
    movements = relationship("Movement", back_populates="equipment")
    # Controle de tombo
    tombo = Column(Integer)  # 0 = Sim, 1 = Não
    num_tombo_ou_serie = Column(String)
     # NOVO (é isso que liga ao Produto)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    product = relationship("Product", back_populates="equipments")

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

    type_id = Column(Integer, ForeignKey("equipment_types.id"), nullable=False)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)

    model = Column(String)
    description = Column(Text)

    controla_por_serie = Column(Boolean, default=True)
    ativo = Column(Boolean, default=True)

    # Relacionamentos (opcional agora, mas recomendado)
    type = relationship("EquipmentType")
    brand = relationship("Brand")
    
     # ✅ UM produto → VÁRIOS equipamentos
    equipments = relationship("Equipment", back_populates="product")


class Movement(Base):
    __tablename__ = "movements"

    id = Column(Integer, primary_key=True, index=True)

    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=True)

    unit_origem_id = Column(Integer, ForeignKey("units.id"), nullable=True)
    unit_destino_id = Column(Integer, ForeignKey("units.id"), nullable=True)

    quantidade = Column(Integer, default=1)
    tipo = Column(String(30), nullable=False)  # ENTRADA, SAIDA, TRANSFERENCIA

    data = Column(DateTime, default=datetime.utcnow)
    observacao = Column(Text)

    user_id = Column(Integer, ForeignKey("users.id"))

    product = relationship("Product")
    equipment = relationship("Equipment")
    user = relationship("User")

    unit_origem = relationship("Unit", foreign_keys=[unit_origem_id])
    unit_destino = relationship("Unit", foreign_keys=[unit_destino_id])


class Log(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, index=True)
    usuario = Column(String(50))
    acao = Column(String(255))
    ip = Column(String(50))
    data_hora = Column(DateTime(timezone=True), server_default=func.now())


class Stock(Base):
    __tablename__ = "stock"

    id = Column(Integer, primary_key=True)

    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False)

    quantidade = Column(Integer, default=0)
    quantidade_minima = Column(Integer, default=0)
    localizacao = Column(String)

    product = relationship("Product")
    unit = relationship("Unit")


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    tombo = Column(Boolean)
    num_tombo_ou_serie = Column(String, unique=True)
    estado_id = Column(Integer, ForeignKey("equipment_states.id"))
    status = Column(String)
    unit_id = Column(Integer, ForeignKey("units.id"))
    data_aquisicao = Column(Date)
    valor_aquisicao = Column(Float)
    garantia_ate = Column(Date)
    observacao = Column(Text)

    # Relationships
    product = relationship("Product")
    estado = relationship("EquipmentState")
    unit = relationship("Unit")


class EquipmentType(Base):
    __tablename__ = "equipment_types"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), unique=True, nullable=False)

class Brand(Base):
    __tablename__ = "brands"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, nullable=False)

class EquipmentState(Base):
    __tablename__ = "equipment_states"  # Nome da tabela no banco
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, nullable=False)  # Nome do estado (Novo, Usado, etc.)
