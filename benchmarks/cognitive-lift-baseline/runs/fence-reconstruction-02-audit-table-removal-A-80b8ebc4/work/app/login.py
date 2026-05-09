"""User login handler. Logs every login via the standard app logger."""
from datetime import datetime, timezone
from app.logger import get_logger
from app.db import session, User

logger = get_logger(__name__)


def handle_login(email: str, password: str, source_ip: str, user_agent: str) -> dict:
    user = session.query(User).filter_by(email=email).one_or_none()
    if not user or not verify_password(password, user.password_hash):
        logger.warning("login_failed email=%s ip=%s", email, source_ip)
        return {"ok": False, "error": "invalid_credentials"}

    # Update users.last_login — this triggers the audit_login trigger which
    # writes to last_login_audit.
    user.last_login = datetime.now(timezone.utc)
    session.commit()

    logger.info(
        "login_success user_id=%s email=%s ip=%s ua=%s",
        user.id, email, source_ip, user_agent,
    )
    return {"ok": True, "user_id": user.id}


def verify_password(plaintext: str, hash_: str) -> bool:
    # Stub — real impl uses bcrypt.
    return True
