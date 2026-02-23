from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, Float, Date, ForeignKey, func
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime


# =====================================================
# USER
# =====================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(100), nullable=False)
    email = Column(String(120), nullable=False, unique=True)
    password = Column(String(100), nullable=False)
    role = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)

    movements = relationship("Movement", back_populates="user")

    def __str__(self):
        return self.username


# =====================================================
# UNIT
# =====================================================

class Unit(Base):
    __tablename__ = "units"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), unique=True, nullable=False)
    manager = Column(String(100), nullable=False)

    stocks = relationship("Stock", back_populates="unit")
    items = relationship("Item", back_populates="unit")

    def __str__(self):
        return self.name


# =====================================================
# PRODUCT
# =====================================================

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    type_id = Column(Integer, ForeignKey("equipment_types.id"), nullable=False)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)

    model = Column(String)
    description = Column(Text)

    controla_por_serie = Column(Boolean, default=True)
    ativo = Column(Boolean, default=True)

    # NOVOS CAMPOS
    quantidade = Column(Integer, default=0)
    quantidade_minima = Column(Integer, default=0)

    # RELACIONAMENTOS
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
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False)

    tombo = Column(Boolean, default=False)
    num_tombo_ou_serie = Column(String, unique=True)

    estado_id = Column(Integer, ForeignKey("equipment_states.id"))
    status = Column(String, default="Disponível")

    data_aquisicao = Column(Date)
    valor_aquisicao = Column(Float)
    garantia_ate = Column(Date)
    observacao = Column(Text)

    product = relationship("Product", back_populates="items")
    estado = relationship("EquipmentState")
    unit = relationship("Unit", back_populates="items")


# =====================================================
# STOCK (Produto sem série)
# =====================================================

class Stock(Base):
    __tablename__ = "stock"

    id = Column(Integer, primary_key=True)

    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False)

    quantidade = Column(Integer, default=0)
    quantidade_minima = Column(Integer, default=0)
    localizacao = Column(String)

    product = relationship("Product", back_populates="stocks")
    unit = relationship("Unit", back_populates="stocks")


# =====================================================
# MOVEMENT
# =====================================================

class Movement(Base):
    __tablename__ = "movements"

    id = Column(Integer, primary_key=True)

    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=True)

    unit_origem_id = Column(Integer, ForeignKey("units.id"), nullable=True)
    unit_destino_id = Column(Integer, ForeignKey("units.id"), nullable=True)

    quantidade = Column(Integer, default=1)
    tipo = Column(String(30), nullable=False)

    data = Column(DateTime, default=datetime.utcnow)
    observacao = Column(Text)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # RELACIONAMENTOS
    product = relationship("Product")
    item = relationship("Item")
    user = relationship("User", back_populates="movements")

    unit_origem = relationship("Unit", foreign_keys=[unit_origem_id])
    unit_destino = relationship("Unit", foreign_keys=[unit_destino_id])


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
