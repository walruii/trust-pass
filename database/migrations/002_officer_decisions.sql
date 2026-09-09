BEGIN;

ALTER TABLE applications
    ADD COLUMN IF NOT EXISTS decision_note TEXT;

COMMIT;
