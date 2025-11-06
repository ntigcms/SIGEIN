# Pydantic models
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UserCreate(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class EquipmentBase(BaseModel):
    name: str
    serial_number: str
    location: str
    status: Optional[str] = "Disponível"
    assigned_to: Optional[str] = None

class EquipmentCreate(EquipmentBase):
    pass

class EquipmentUpdate(BaseModel):
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    location: Optional[str] = None

class EquipmentResponse(EquipmentBase):
    id: int
    class Config:
        orm_mode = True

class EquipmentLogResponse(BaseModel):
    id: int
    equipment_id: int
    action: str
    timestamp: datetime
    user: str
    class Config:
        orm_mode = True
