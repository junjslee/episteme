"""Tests for core/practice/quality observation generation."""
from __future__ import annotations

from core.practice.quality import (
    PracticeObservation,
    PracticeRetrospective,
    observe_surface,
    observe_surfaces,
)


def _make_minimal_irreversible_surface() -> dict:
    """A bare-bones irreversible surface with lazy fields — should trigger many observations."""
    return {
        "envelope": {"surface_id": "surf-minimal-001"},
        "surface": {
            "core_question": "tbd",  # lazy
            "risk_classification": {
                "reversibility": "irreversible",
                "blast_radius": "regulated_artifact",
                "ai_act_tier": "high",
                "article_79_1_triggers": [],
            },
            "knowns": [],
            "unknowns": [],
            "assumptions": [],
            "disconfirmation_conditions": [],
            "decision": {
                "choice": "proceed",
                "confidence": 0.3,
                "stop_rollback_path": "rollback",  # < 20 chars
            },
        },
    }


def _make_well_practiced_surface() -> dict:
    """A surface with concrete fields — should trigger few/no observations."""
    return {
        "envelope": {"surface_id": "surf-good-001"},
        "surface": {
            "core_question": "Should I run the migration on prod-us-east now during business hours?",
            "risk_classification": {
                "reversibility": "irreversible",
                "blast_radius": "regulated_artifact",
                "ai_act_tier": "high",
                "article_79_1_triggers": ["material_user_impact"],
            },
            "knowns": [
                {
                    "fact": "Staging dry-run passed at 14:09 UTC.",
                    "source_artifact": "test://ci-run/2026-05-12/staging-mirror",
                    "verified_at": "2026-05-12T14:09:00Z",
                    "verification_method": "test_pass",
                }
            ],
            "unknowns": [
                {
                    "unknown": "Whether out-of-band schema changes were applied to prod-us-east in the last 30 days.",
                    "why_not_resolvable_now": "Schema audit log retention reduced to 14d; the 14d gap is unrecorded.",
                    "cost_of_ignorance": "Migration may acquire AccessExclusiveLock for several minutes if column ordering drifted; SLA breach in business hours.",
                }
            ],
            "assumptions": [
                {
                    "assumption": "Read replica failover is configured for prod-us-east.",
                    "if_wrong_then": "p99 latency spikes during the migration window; potential 30-90 second 5xx outage.",
                    "detectability": "post_execution_soft",
                }
            ],
            "disconfirmation_conditions": [
                {
                    "observable": "lock_wait_seconds > 0.5 in first 5 seconds of migration",
                    "measurement_method": "pg_stat_activity polled at 1Hz",
                    "would_invalidate_plan": True,
                }
            ],
            "decision": {
                "choice": "proceed",
                "confidence": 0.78,
                "stop_rollback_path": "psql -c 'SELECT pg_cancel_backend(pid)' against migration session",
            },
        },
    }


def test_observe_minimal_irreversible_finds_many_gaps():
    obs = observe_surface(_make_minimal_irreversible_surface())
    # Lazy core_question, empty unknowns, empty assumptions, empty disconfirmation,
    # short rollback path, low confidence on irreversible proceed.
    assert len(obs) >= 4
    move_ids_hit = {o.move_id for o in obs}
    assert "frame.core_question" in move_ids_hit
    assert "frame.unknowns" in move_ids_hit
    assert "verify.disconfirmation_conditions" in move_ids_hit


def test_observe_well_practiced_surface_clean_or_minor():
    obs = observe_surface(_make_well_practiced_surface())
    # All required fields populated with substantive content; no critical observations expected.
    critical_obs = [o for o in obs if o.severity == "critical"]
    assert len(critical_obs) == 0


def test_observe_minimal_includes_severity_levels():
    obs = observe_surface(_make_minimal_irreversible_surface())
    severities = {o.severity for o in obs}
    # Should have at least one critical observation given lazy core_question on irreversible
    assert "critical" in severities or "warn" in severities


def test_observe_surface_returns_practice_observation_instances():
    obs = observe_surface(_make_minimal_irreversible_surface())
    for o in obs:
        assert isinstance(o, PracticeObservation)
        assert o.move_id
        assert o.summary
        assert o.detail
        assert o.severity in {"info", "advisory", "warn", "critical"}


def test_observe_surface_attaches_surface_id():
    obs = observe_surface(_make_minimal_irreversible_surface())
    for o in obs:
        assert o.surface_id == "surf-minimal-001"


def test_observe_surfaces_aggregates_retrospective():
    surfaces = [
        _make_minimal_irreversible_surface(),
        _make_minimal_irreversible_surface(),
        _make_well_practiced_surface(),
    ]
    retro = observe_surfaces(surfaces)
    assert isinstance(retro, PracticeRetrospective)
    assert retro.surfaces_examined == 3
    # Minimal surface should hit frame.unknowns + others repeatedly → most_frequent_gaps populated
    assert len(retro.most_frequent_gaps) > 0
    assert "frame.unknowns" in retro.most_frequent_gaps or "frame.core_question" in retro.most_frequent_gaps


def test_observe_surfaces_empty_window():
    retro = observe_surfaces([])
    assert retro.surfaces_examined == 0
    assert retro.observations == []
    assert retro.most_frequent_gaps == []


def test_observation_to_dict_round_trip():
    obs = observe_surface(_make_minimal_irreversible_surface())
    for o in obs:
        d = o.to_dict()
        assert d["move_id"] == o.move_id
        assert d["severity"] == o.severity
        assert d["summary"] == o.summary


def test_retrospective_to_dict_includes_counts():
    retro = observe_surfaces([_make_minimal_irreversible_surface()])
    d = retro.to_dict()
    assert d["surfaces_examined"] == 1
    assert "move_gap_counts" in d
    assert "most_frequent_gaps" in d


def test_high_tier_without_article_79_triggers_observed():
    surface = _make_well_practiced_surface()
    # Strip the Article 79(1) triggers
    surface["surface"]["risk_classification"]["article_79_1_triggers"] = []
    obs = observe_surface(surface)
    move_ids = {o.move_id for o in obs}
    assert "frame.constraint_regime" in move_ids


def test_low_confidence_irreversible_proceed_observed():
    surface = _make_well_practiced_surface()
    surface["surface"]["decision"]["confidence"] = 0.3  # low
    obs = observe_surface(surface)
    move_ids = {o.move_id for o in obs}
    assert "decompose.hypothesis_as_bet" in move_ids
