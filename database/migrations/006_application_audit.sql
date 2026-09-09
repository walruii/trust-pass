BEGIN;

CREATE TABLE IF NOT EXISTS application_audit_events (
    id VARCHAR(36) PRIMARY KEY,
    application_id VARCHAR(36) REFERENCES applications(id) ON DELETE CASCADE,
    actor_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
    event_type VARCHAR(64) NOT NULL,
    from_status VARCHAR(32),
    to_status VARCHAR(32),
    note TEXT,
    details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_application_audit_events_application_id
    ON application_audit_events (application_id);

CREATE INDEX IF NOT EXISTS ix_application_audit_events_actor_id
    ON application_audit_events (actor_id);

CREATE INDEX IF NOT EXISTS ix_application_audit_events_created_at
    ON application_audit_events (created_at);

COMMIT;
