-- Add learning-material fields to diagrams table
-- Safe to run multiple times

ALTER TABLE diagrams
ADD COLUMN IF NOT EXISTS description TEXT,
ADD COLUMN IF NOT EXISTS path_pdf VARCHAR(1000);

-- Optional: simple index to speed search/filter by pdf path
CREATE INDEX IF NOT EXISTS idx_diagrams_path_pdf ON diagrams(path_pdf);
