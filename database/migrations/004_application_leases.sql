BEGIN;

ALTER TABLE applications
    ADD COLUMN IF NOT EXISTS decision_by VARCHAR(36),
    ADD COLUMN IF NOT EXISTS decision_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS application_leases (
    id VARCHAR(36) PRIMARY KEY,
    application_id VARCHAR(36) NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    officer_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    claim_token VARCHAR(64) NOT NULL UNIQUE,
    claimed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    lease_expires_at TIMESTAMPTZ NOT NULL,
    released_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_application_leases_application_id
    ON application_leases (application_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_active_application_lease
    ON application_leases (application_id)
    WHERE released_at IS NULL;

COMMIT;
