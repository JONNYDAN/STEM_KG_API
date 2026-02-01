-- PostgreSQL auto-code triggers for STEM_KG_API
-- Run this script AFTER tables are created.

-- 1) Helper counter table and function
CREATE TABLE IF NOT EXISTS code_counters (
    key TEXT PRIMARY KEY,
    last_value INTEGER NOT NULL
);

CREATE OR REPLACE FUNCTION next_code_value(p_key TEXT)
RETURNS INTEGER AS $$
DECLARE
    v INTEGER;
BEGIN
    SELECT last_value INTO v FROM code_counters WHERE key = p_key FOR UPDATE;
    IF NOT FOUND THEN
        v := 1;
        INSERT INTO code_counters(key, last_value) VALUES (p_key, v);
    ELSE
        v := v + 1;
        UPDATE code_counters SET last_value = v WHERE key = p_key;
    END IF;
    RETURN v;
END;
$$ LANGUAGE plpgsql;

-- 2) Categories: CAT-{root}-{level}-{seq}
ALTER TABLE categories
    ADD COLUMN IF NOT EXISTS code VARCHAR(50),
    ADD COLUMN IF NOT EXISTS level INTEGER DEFAULT 1;

CREATE OR REPLACE FUNCTION trg_categories_code()
RETURNS TRIGGER AS $$
DECLARE
    root_code TEXT;
    seq INTEGER;
    lvl INTEGER;
BEGIN
    IF NEW.level IS NULL THEN
        NEW.level := 1;
    END IF;

    IF NEW.code IS NULL OR NEW.code = '' THEN
        root_code := COALESCE(NEW.root_category_id, 'UNK');
        lvl := NEW.level;
        seq := next_code_value(format('CAT-%s-%s', root_code, lvl));
        NEW.code := format('CAT-%s-%s-%s', root_code, lvl, lpad(seq::TEXT, 2, '0'));
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS categories_code_trigger ON categories;
CREATE TRIGGER categories_code_trigger
BEFORE INSERT ON categories
FOR EACH ROW
EXECUTE FUNCTION trg_categories_code();

CREATE UNIQUE INDEX IF NOT EXISTS ux_categories_code ON categories(code);

-- 3) Diagrams: DGM-{category}-{sequence}
CREATE OR REPLACE FUNCTION trg_diagrams_id()
RETURNS TRIGGER AS $$
DECLARE
    cat_code TEXT;
    seq INTEGER;
BEGIN
    IF NEW.id IS NULL OR NEW.id = '' THEN
        SELECT c.code INTO cat_code
        FROM categories c
        WHERE c.id = NEW.category_id;

        cat_code := COALESCE(cat_code, 'UNK');
        seq := next_code_value(format('DGM-%s', cat_code));
        NEW.id := format('DGM-%s-%s', cat_code, lpad(seq::TEXT, 3, '0'));
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS diagrams_id_trigger ON diagrams;
CREATE TRIGGER diagrams_id_trigger
BEFORE INSERT ON diagrams
FOR EACH ROW
EXECUTE FUNCTION trg_diagrams_id();

-- 4) Subjects (Objects): OBJ-{type}-{hash}
ALTER TABLE subjects
    ADD COLUMN IF NOT EXISTS code VARCHAR(50);

CREATE OR REPLACE FUNCTION trg_subjects_code()
RETURNS TRIGGER AS $$
DECLARE
    root_name TEXT;
    type_code TEXT;
    hash_code TEXT;
BEGIN
    IF NEW.code IS NULL OR NEW.code = '' THEN
        IF NEW.root_subject_id IS NOT NULL THEN
            SELECT rs.name INTO root_name
            FROM root_subjects rs
            WHERE rs.id = NEW.root_subject_id;
        END IF;

        type_code := upper(substr(regexp_replace(COALESCE(root_name, 'UNK'), '[^A-Za-z]', '', 'g'), 1, 3));
        IF length(type_code) < 3 THEN
            type_code := rpad(type_code, 3, 'X');
        END IF;

        hash_code := upper(substr(md5(COALESCE(NEW.name, ''))::TEXT, 1, 4));
        NEW.code := format('OBJ-%s-%s', type_code, hash_code);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS subjects_code_trigger ON subjects;
CREATE TRIGGER subjects_code_trigger
BEFORE INSERT ON subjects
FOR EACH ROW
EXECUTE FUNCTION trg_subjects_code();

CREATE UNIQUE INDEX IF NOT EXISTS ux_subjects_code ON subjects(code);

-- 5) Relationships: REL-{timestamp}-{seq}
ALTER TABLE relationships
    ADD COLUMN IF NOT EXISTS code VARCHAR(50);

CREATE OR REPLACE FUNCTION trg_relationships_code()
RETURNS TRIGGER AS $$
DECLARE
    month_key TEXT;
    seq INTEGER;
BEGIN
    IF NEW.code IS NULL OR NEW.code = '' THEN
        month_key := to_char(now(), 'YYYYMM');
        seq := next_code_value(format('REL-%s', month_key));
        NEW.code := format('REL-%s-%s', month_key, lpad(seq::TEXT, 3, '0'));
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS relationships_code_trigger ON relationships;
CREATE TRIGGER relationships_code_trigger
BEFORE INSERT ON relationships
FOR EACH ROW
EXECUTE FUNCTION trg_relationships_code();

CREATE UNIQUE INDEX IF NOT EXISTS ux_relationships_code ON relationships(code);
