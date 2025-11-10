from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
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
    name = Column(String, unique=True)
    manager = Column(String)

class Equipment(Base):
    __tablename__ = "equipments"
    id = Column(Integer, primary_key=True, index=True)
    # nome = Column(String, nullable=False)
    tipo_id = Column(Integer, ForeignKey("equipment_types.id"), nullable=False)  # Chave estrangeira
    brand = Column(String)
    status = Column(String)
    state = Column(String)
    location = Column(String)
    tombo = Column(Integer, default=1)  # 0 = Sim, 1 = Não
    num_tombo_ou_serie = Column(String, nullable=True)
    
    tipo = relationship("EquipmentType")  # Relacionamento com EquipmentType
    movements = relationship("Movement", back_populates="equipment")

class Movement(Base):
    __tablename__ = "movements"
    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipments.id"))  # ✅ corrigido
    user_id = Column(Integer, ForeignKey("users.id"))
    date = Column(DateTime, default=datetime.utcnow)
    type = Column(String)
    equipment = relationship("Equipment", back_populates="movements")
    user = relationship("User", back_populates="movements")

class Log(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, index=True)
    usuario = Column(String(50))
    acao = Column(String(255))
    ip = Column(String(50))
    data_hora = Column(DateTime(timezone=True), server_default=func.now())

class EquipmentType(Base):
    __tablename__ = "equipment_types"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), unique=True, nullable=False)
