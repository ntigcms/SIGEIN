from database import SessionLocal
from models import Equipment, Product

db = SessionLocal()

equipments = db.query(Equipment).all()

for eq in equipments:
    product = db.query(Product).filter(
        Product.type_id == eq.tipo_id,
        Product.brand_id == eq.brand_id
    ).first()

    if not product:
        product = Product(
            name=f"Produto automático ({eq.id})",
            type_id=eq.tipo_id,
            brand_id=eq.brand_id,
            controla_por_serie=True
        )
        db.add(product)
        db.commit()
        db.refresh(product)

    eq.product_id = product.id

db.commit()
db.close()
