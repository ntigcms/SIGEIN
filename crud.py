from models import Equipment, Log, User

def get_equipments(db):
    return db.query(Equipment).all()

def get_equipment(db, equipment_id):
    return db.query(Equipment).filter(Equipment.id == equipment_id).first()

def create_equipment(db, name, serial_number, location, status, assigned_to, user):
    eq = Equipment(name=name, serial_number=serial_number, location=location, status=status, assigned_to=assigned_to)
    db.add(eq)
    db.commit()
    db.refresh(eq)
    log_action(db, f"Equipamento {name} adicionado", user)
    return eq

def update_equipment(db, equipment_id, name, serial_number, location, status, assigned_to, user):
    eq = get_equipment(db, equipment_id)
    if eq:
        eq.name = name
        eq.serial_number = serial_number
        eq.location = location
        eq.status = status
        eq.assigned_to = assigned_to
        db.commit()
        log_action(db, f"Equipamento {name} atualizado", user)
    return eq

def delete_equipment(db, equipment_id, user):
    eq = get_equipment(db, equipment_id)
    if eq:
        db.delete(eq)
        db.commit()
        log_action(db, f"Equipamento {eq.name} removido", user)
    return eq

def log_action(db, action, user):
    log = Log(action=action, user=user)
    db.add(log)
    db.commit()
