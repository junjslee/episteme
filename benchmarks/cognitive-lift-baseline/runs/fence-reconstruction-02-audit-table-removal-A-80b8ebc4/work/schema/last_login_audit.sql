-- Append-only audit table for user logins.
-- Row inserted on every login via the audit_login trigger.
CREATE TABLE last_login_audit (
    audit_id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    login_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_ip INET,
    user_agent TEXT,
    -- 7-year retention enforced via lifecycle policy on the table
    retain_until TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '7 years'
);

CREATE INDEX last_login_audit_user_idx ON last_login_audit(user_id);
CREATE INDEX last_login_audit_retain_until_idx ON last_login_audit(retain_until);
