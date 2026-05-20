-- Vincula marcas a categoria e tipo de equipamento
ALTER TABLE brands DROP CONSTRAINT IF EXISTS brands_nome_key;

ALTER TABLE brands ADD COLUMN IF NOT EXISTS category_id INTEGER REFERENCES categories(id);
ALTER TABLE brands ADD COLUMN IF NOT EXISTS type_id INTEGER REFERENCES equipment_types(id);

ALTER TABLE brands DROP CONSTRAINT IF EXISTS uq_brand_nome_cat_tipo;
ALTER TABLE brands ADD CONSTRAINT uq_brand_nome_cat_tipo UNIQUE (nome, category_id, type_id);
