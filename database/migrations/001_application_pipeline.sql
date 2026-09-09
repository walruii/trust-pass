BEGIN;

CREATE TABLE IF NOT EXISTS applications (
    id VARCHAR(36) PRIMARY KEY,
    kiosk_id VARCHAR(100) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'QUEUED',
    pipeline_version VARCHAR(32) NOT NULL DEFAULT '1.0',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    result_json JSONB,
    error_message TEXT,
    processing_started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS application_images (
    id SERIAL PRIMARY KEY,
    application_id VARCHAR(36) NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    image_type VARCHAR(16) NOT NULL,
    mime_type VARCHAR(64) NOT NULL,
    image_bytes BYTEA NOT NULL,
    byte_size INTEGER NOT NULL,
    sha256 VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE applications
    ADD COLUMN IF NOT EXISTS result_json JSONB,
    ADD COLUMN IF NOT EXISTS processing_started_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS ix_applications_kiosk_id
    ON applications (kiosk_id);

CREATE INDEX IF NOT EXISTS ix_applications_status
    ON applications (status);

CREATE INDEX IF NOT EXISTS ix_application_images_application_id
    ON application_images (application_id);

COMMIT;
