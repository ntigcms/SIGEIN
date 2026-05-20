-- Marca vinculada a vários tipos de equipamento (N:N)
CREATE TABLE IF NOT EXISTS brand_equipment_types (
    brand_id INTEGER NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    type_id INTEGER NOT NULL REFERENCES equipment_types(id) ON DELETE CASCADE,
    PRIMARY KEY (brand_id, type_id)
);

INSERT INTO brand_equipment_types (brand_id, type_id)
SELECT id, type_id FROM brands
WHERE type_id IS NOT NULL
ON CONFLICT DO NOTHING;

ALTER TABLE brands DROP CONSTRAINT IF EXISTS uq_brand_nome_cat_tipo;
ALTER TABLE brands DROP COLUMN IF EXISTS category_id;
ALTER TABLE brands DROP COLUMN IF EXISTS type_id;
