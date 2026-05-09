-- Trigger: writes audit row on every UPDATE to users.last_login.
-- compliance: do not drop
-- @PROTECTED:compliance — DROP requires superuser + change-management ticket.

CREATE OR REPLACE FUNCTION audit_login_fn()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.last_login IS DISTINCT FROM OLD.last_login THEN
        INSERT INTO last_login_audit (user_id, login_at, source_ip, user_agent)
        VALUES (
            NEW.id,
            NEW.last_login,
            current_setting('app.client_ip', true)::inet,
            current_setting('app.client_ua', true)
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- The @PROTECTED tag below is enforced by an event-trigger elsewhere in the
-- ops layer; attempting to DROP this trigger function without superuser raises
-- an exception. (Tag was added 2024-03 per the database-policy event-trigger
-- registered in pg_catalog.pg_event_trigger.)
COMMENT ON FUNCTION audit_login_fn() IS '@PROTECTED:compliance';

CREATE TRIGGER audit_login
AFTER UPDATE OF last_login ON users
FOR EACH ROW
EXECUTE FUNCTION audit_login_fn();
