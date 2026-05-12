"""`episteme practice demo` — output a worked-example signed surface narrated.

The demo surface walks through a realistic irreversible-action scenario
(database migration on production) and produces a fully-fleshed-out
signed surface body, with narration showing which cognitive move each
field represents and why each field's content is well-practiced rather
than placeholder.

The demo does NOT sign or persist. It outputs the body to stdout for
inspection. Operators can copy the JSON into a body-file and run
`episteme surface sign body.json` if they want to sign and persist.
"""
from __future__ import annotations

# pyright: reportMissingImports=false
import json
from typing import Any, Dict

from episteme import _ui


def demo_surface_body() -> Dict[str, Any]:
    """A worked-example surface body. Fully practiced, no lazy fields."""
    return {
        "core_question": (
            "Should I run the migration to add NOT NULL on users.email on "
            "prod-us-east during business hours?"
        ),
        "risk_classification": {
            "reversibility": "irreversible",
            "blast_radius": "regulated_artifact",
            "ai_act_tier": "high",
            "article_79_1_triggers": [
                "material_user_impact",
                "non_recoverable_state_change",
            ],
        },
        "knowns": [
            {
                "fact": "Staging dry-run completed with 0 row-size violations on a snapshot taken 6 hours ago.",
                "source_artifact": "test://ci-run/2026-05-12/migration-dry-run-staging",
                "verified_at": "2026-05-12T14:09:00.000Z",
                "verification_method": "test_pass",
            },
            {
                "fact": "Migration acquires AccessExclusiveLock on users; expected lock duration on staging 0.4s.",
                "source_artifact": "test://ci-run/2026-05-12/migration-lock-duration-staging",
                "verified_at": "2026-05-12T14:11:00.000Z",
                "verification_method": "test_pass",
            },
        ],
        "unknowns": [
            {
                "unknown": "Whether out-of-band schema changes were applied to prod-us-east since the last staging-sync.",
                "why_not_resolvable_now": "Schema audit log retention reduced to 14d after Feb 2026 cost cutting; the 14d gap window is unrecorded.",
                "cost_of_ignorance": "Migration may acquire AccessExclusiveLock on a 280M-row table for several minutes if column ordering drifted; SLA breach in business hours.",
            },
            {
                "unknown": "Whether the connection pooler will reroute reads to a replica during the lock window.",
                "why_not_resolvable_now": "Pooler config is in a separate repo with no documented test; haven't checked since last quarter.",
                "cost_of_ignorance": "Reads may block during lock, causing user-facing p99 latency spike and potential 5xx storm before manual failover.",
            },
        ],
        "assumptions": [
            {
                "assumption": "Read replica failover is configured and tested for prod-us-east.",
                "if_wrong_then": "User-facing read latency p99 spikes above SLA during the migration window; potential 5xx outage of 30-90 seconds.",
                "detectability": "post_execution_soft",
            },
            {
                "assumption": "No application code reads users.email expecting a possible NULL value.",
                "if_wrong_then": "Constraint failure on existing rows where email was set to empty-string instead of NULL; migration partially commits then fails.",
                "detectability": "pre_execution",
            },
        ],
        "disconfirmation_conditions": [
            {
                "observable": "lock_wait_seconds > 0.5 in the first 5 seconds of migration",
                "measurement_method": "pg_stat_activity polled at 1Hz, alert via the deploy dashboard's lock-monitor row",
                "would_invalidate_plan": True,
            },
            {
                "observable": "Any users.email row exists with empty-string value when checked pre-migration",
                "measurement_method": "SELECT COUNT(*) FROM users WHERE email = '' on read replica, expected 0",
                "would_invalidate_plan": True,
            },
        ],
        "decision": {
            "choice": "proceed",
            "confidence": 0.78,
            "confidence_elicitation_method": "written_probability_estimate",
            "stop_rollback_path": (
                "psql -c \"SELECT pg_cancel_backend(pid)\" against the migration session; "
                "if commit already partially applied, run rollback migration 0043b which "
                "drops the NOT NULL constraint without table rewrite (tested on staging)."
            ),
        },
        "audit": {
            "blueprint_invoked": "consequence_chain",
            "validation_layers_passed": [
                "presence",
                "freshness",
                "signature",
                "completeness",
                "non_lazy",
                "chain_integrity",
                "classifier_clean",
                "confidence_elicited",
            ],
        },
    }


def run_demo(*, format_: str = "narrated") -> int:
    """Print the worked-example surface body."""
    body = demo_surface_body()

    if format_ == "json":
        print(json.dumps(body, indent=2, sort_keys=True))
        return 0

    # Narrated mode
    print()
    print(_ui.header("episteme · worked example", level=1, color="cyan"))
    print()
    print("This is what a well-practiced Reasoning Surface body looks like before signing.")
    print("Every field is the residue of a specific cognitive move (see `episteme practice walk`).")
    print()
    print(_ui.colored("Not lazy. Not placeholder. Not 'TBD'. This is what the practice actually produces.", "grey"))
    print()
    print(_ui.divider())
    print()

    # ── Core Question ──
    print(_ui.header("Core Question (Frame · question-substitution counter)", level=2, color="cyan"))
    print(f"  → {body['core_question']}")
    print()

    # ── Risk classification ──
    rc = body["risk_classification"]
    print(_ui.header("Risk Classification (Frame · reversibility + constraint regime)", level=2, color="cyan"))
    print(f"  reversibility:  {rc['reversibility']}")
    print(f"  blast_radius:   {rc['blast_radius']}")
    print(f"  ai_act_tier:    {rc['ai_act_tier']}")
    print(f"  79(1) triggers: {', '.join(rc['article_79_1_triggers'])}")
    print()

    # ── Knowns ──
    print(_ui.header("Knowns (Frame · narrative-fallacy counter)", level=2, color="cyan"))
    print(_ui.colored("  Each known has a source artifact + verification method. No 'I think' here.", "grey"))
    for i, k in enumerate(body["knowns"], 1):
        print(f"  [{i}] {k['fact']}")
        print(_ui.colored(f"      source:   {k['source_artifact']}", "grey"))
        print(_ui.colored(f"      verified: {k['verified_at']} via {k['verification_method']}", "grey"))
    print()

    # ── Unknowns ──
    print(_ui.header("Unknowns (Frame · WYSIATI counter)", level=2, color="cyan"))
    print(_ui.colored("  Each unknown has a real cost_of_ignorance — the utility filter.", "grey"))
    for i, u in enumerate(body["unknowns"], 1):
        print(f"  [{i}] {u['unknown']}")
        print(_ui.colored(f"      why not resolvable: {u['why_not_resolvable_now']}", "grey"))
        print(_ui.colored(f"      cost of ignorance:  {u['cost_of_ignorance']}", "grey"))
    print()

    # ── Assumptions ──
    print(_ui.header("Assumptions (Frame · overconfidence counter)", level=2, color="cyan"))
    print(_ui.colored("  Each assumption names if_wrong_then + detectability.", "grey"))
    for i, a in enumerate(body["assumptions"], 1):
        print(f"  [{i}] {a['assumption']}")
        print(_ui.colored(f"      if wrong:       {a['if_wrong_then']}", "grey"))
        print(_ui.colored(f"      detectability:  {a['detectability']}", "grey"))
    print()

    # ── Disconfirmation ──
    print(_ui.header("Disconfirmation (Verify · robust falsifiability)", level=2, color="cyan"))
    print(_ui.colored("  Pre-committed observables. 'If issues arise' would fail.", "grey"))
    for i, d in enumerate(body["disconfirmation_conditions"], 1):
        print(f"  [{i}] OBSERVABLE: {d['observable']}")
        print(_ui.colored(f"      MEASURE:    {d['measurement_method']}", "grey"))
    print()

    # ── Decision ──
    dec = body["decision"]
    print(_ui.header("Decision (Decompose · hypothesis-as-bet + Handoff · rollback)", level=2, color="cyan"))
    print(f"  choice:     {dec['choice']}")
    print(f"  confidence: {dec['confidence']} (via {dec['confidence_elicitation_method']})")
    print(f"  rollback:")
    print(f"    {dec['stop_rollback_path']}")
    print()

    print(_ui.divider())
    print()
    print("This body is what `episteme surface author --interactive` produces when the")
    print("operator practices each stage. To sign + persist this exact body:")
    print()
    print(_ui.colored("  $ episteme practice demo --format json > demo_body.json", "cyan"))
    print(_ui.colored("  $ episteme surface sign demo_body.json --with-tsa --with-rekor", "cyan"))
    print()
    return 0
