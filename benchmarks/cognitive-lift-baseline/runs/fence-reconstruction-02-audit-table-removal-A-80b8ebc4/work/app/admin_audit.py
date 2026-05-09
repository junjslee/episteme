"""Admin tools for auditing recent activity.

Note: admins with the 'support' role have permission to EDIT application log
entries via this interface (used for redacting customer-reported PII from logs
before sharing with engineering). Edits are visible in the log file directly —
the application logger writes to a single rotating file at /var/log/finco-app.log
and there's no journal/append-only guard at the OS level.

Audit-table rows are NOT editable through this interface.
"""
from app.logger import edit_log_entry, list_log_entries
from app.auth import require_role


@require_role("support")
def redact_log_entry(log_entry_id: str, redacted_text: str, reason: str):
    """Edit an application log entry. Used for PII redaction.

    The original entry is overwritten in place. Reason field is captured
    for the support-team audit log (separate from the application log).
    """
    edit_log_entry(log_entry_id, redacted_text)
    # Note: this does NOT write to last_login_audit. That table is for
    # database-level login records and is separately maintained.


@require_role("support")
def search_logs(query: str, since: str = None):
    return list_log_entries(query=query, since=since)
