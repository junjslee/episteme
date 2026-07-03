"""Semantic-tier promotion job — episodic records → semantic proposals.

Implements phase 11 of the 0.11.0 plan and the promotion contract declared
in `kernel/MEMORY_ARCHITECTURE.md` ("episodic → semantic" section). Never
writes to the semantic tier directly: proposals land in the reflective
tier for operator review, and only an explicit acceptance step (deferred
to a future phase) promotes a proposal into semantic.

Invariants this module maintains:

1. **Deterministic.** Re-running on the same episodic records produces
   the same proposals (same cluster signatures, same ranked order).
2. **Never auto-promotes.** Writes only to
   ``~/.episteme/memory/reflective/semantic_proposals.jsonl``. The
   semantic tier is never touched.
3. **Never blocks.** Any exception returns an empty-report outcome
   rather than crashing the CLI. Memory analysis must not interfere
   with the operator's cycle.
4. **Preserves existing contracts.** Reads episodic records written by
   ``core/hooks/episodic_writer.py`` without mutating them; records are
   append-only by MEMORY_ARCHITECTURE.md rule.

The clustering pass is intentionally embedding-free (keyword + domain +
action-class match). A more sophisticated clusterer is a later revision;
this first pass is good enough to demonstrate the promotion pipeline
and to feed the phase-12 profile-audit loop with pattern-stability
signals.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


DEFAULT_EPISODIC_DIR = Path.home() / ".episteme" / "memory" / "episodic"
DEFAULT_REFLECTIVE_DIR = Path.home() / ".episteme" / "memory" / "reflective"
DEFAULT_MIN_CLUSTER_SIZE = 3
OUTCOME_STABLE_HIGH = 0.8  # success_rate >= this ⇒ "typically succeeds"
OUTCOME_STABLE_LOW = 0.2   # success_rate <= this ⇒ "typically fails"


@dataclass(frozen=True)
class ClusterSignature:
    """Immutable, hashable cluster key.

    Domain marker + primary action pattern. Frozen so it can be a dict
    key for grouping and so `signature_of(r) == signature_of(r)` is
    stable across runs.
    """

    domain: str
    action_pattern: str

    def as_dict(self) -> dict[str, str]:
        return {"domain": self.domain, "action_pattern": self.action_pattern}

    def display(self) -> str:
        return f"{self.action_pattern} (domain={self.domain})"


# ----- IO -------------------------------------------------------------

def load_episodic_records(episodic_dir: Path) -> list[dict]:
    """Read every .jsonl file under the episodic dir. Malformed lines are
    skipped (never block on a corrupt record). Returns empty list if the
    directory doesn't exist — first-pass writers may not have fired yet.
    """
    if not episodic_dir.is_dir():
        return []
    records: list[dict] = []
    for path in sorted(episodic_dir.glob("*.jsonl")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(record, dict) and record.get("memory_class") == "episodic":
                        records.append(record)
        except OSError:
            continue
    return records


def write_proposals(
    proposals: Sequence[dict],
    reflective_dir: Path,
    *,
    now_iso: str | None = None,
) -> Path | None:
    """Append-write proposals to
    ``<reflective_dir>/semantic_proposals.jsonl``. Returns the path, or
    None when the proposal list is empty (a no-op run must not create an
    empty file, which would muddle the signal that "no promotion
    candidates were found this cycle").
    """
    if not proposals:
        return None
    reflective_dir.mkdir(parents=True, exist_ok=True)
    path = reflective_dir / "semantic_proposals.jsonl"
    ts = now_iso or datetime.now(timezone.utc).isoformat()
    with open(path, "a", encoding="utf-8") as f:
        for proposal in proposals:
            enriched = dict(proposal)
            enriched.setdefault("proposed_at", ts)
            f.write(json.dumps(enriched, ensure_ascii=False, sort_keys=True) + "\n")
    return path


# ----- Clustering -----------------------------------------------------

def signature_of(record: dict) -> ClusterSignature | None:
    """Extract the cluster signature from an episodic record.

    Returns None when the record lacks both a matched pattern and a
    domain marker — those records cannot be meaningfully clustered on
    this pass and shouldn't silently aggregate under a fake "(unknown)"
    signature (that dilutes the signal).
    """
    details = record.get("details") or {}
    surface = details.get("reasoning_surface") if isinstance(details, dict) else None
    domain = "Unknown"
    if isinstance(surface, dict):
        d = surface.get("domain")
        if isinstance(d, str) and d.strip():
            domain = d.strip()
    hits = details.get("high_impact_patterns_matched") if isinstance(details, dict) else None
    if not isinstance(hits, list) or not hits:
        return None
    # Primary pattern is the first matched label — stable across runs
    # because episodic_writer walks the pattern list in declared order.
    primary = str(hits[0]).strip()
    if not primary:
        return None
    return ClusterSignature(domain=domain, action_pattern=primary)


def cluster_records(records: Iterable[dict]) -> dict[ClusterSignature, list[dict]]:
    """Group episodic records by signature. Records with no signature
    (insufficient fields) are silently dropped from the analysis — they
    cannot be clustered on the current similarity dimensions.
    """
    groups: dict[ClusterSignature, list[dict]] = defaultdict(list)
    for record in records:
        sig = signature_of(record)
        if sig is None:
            continue
        groups[sig].append(record)
    return dict(groups)


# ----- Analysis -------------------------------------------------------

def _success_rate(cluster: Sequence[dict]) -> tuple[float, int]:
    """Fraction of records with exit_code == 0. Also returns the count
    of records that carried an exit_code at all — a cluster with no
    observed exits is not informative regardless of its size.
    """
    observed = 0
    successes = 0
    for record in cluster:
        details = record.get("details") or {}
        if not isinstance(details, dict):
            continue
        code = details.get("exit_code")
        if not isinstance(code, int):
            continue
        observed += 1
        if code == 0:
            successes += 1
    if observed == 0:
        return 0.0, 0
    return successes / observed, observed


def _stability_label(rate: float) -> str:
    if rate >= OUTCOME_STABLE_HIGH:
        return "typically-succeeds"
    if rate <= OUTCOME_STABLE_LOW:
        return "typically-fails"
    return "mixed"


def _disconfirmation_fire_rate(cluster: Sequence[dict]) -> tuple[float | None, int]:
    """Fraction of records where the cycle's Disconfirmation condition
    ended up being the actual reason for the non-zero exit. First-pass
    approximation: when exit_code != 0 AND a surface was captured, count
    the record as a "disconfirmation event." This under-reports (misses
    partial fires) but never over-reports — false-positive moves against
    the operator's self-assessment should be the rare direction of
    error. Returns None when nothing can be inferred.
    """
    with_surface_and_exit = 0
    disc_events = 0
    for record in cluster:
        details = record.get("details") or {}
        if not isinstance(details, dict):
            continue
        surface = details.get("reasoning_surface")
        if not isinstance(surface, dict):
            continue
        code = details.get("exit_code")
        if not isinstance(code, int):
            continue
        with_surface_and_exit += 1
        if code != 0:
            disc_events += 1
    if with_surface_and_exit == 0:
        return None, 0
    return disc_events / with_surface_and_exit, with_surface_and_exit


def analyze_cluster(
    signature: ClusterSignature,
    cluster: Sequence[dict],
) -> dict:
    """Produce a deterministic proposal dict for one cluster. The
    returned shape is flat JSON-serializable, suitable for append-write
    to the reflective tier. Evidence refs carry episodic record IDs so
    phase-12 audit can trace back to source.
    """
    success_rate, with_exit = _success_rate(cluster)
    disc_rate, with_surface = _disconfirmation_fire_rate(cluster)
    stability = _stability_label(success_rate)
    evidence_refs = sorted(
        str(r.get("id", "")).strip()
        for r in cluster
        if str(r.get("id", "")).strip()
    )
    # Proposal id is a deterministic hash of (signature, sorted record
    # ids). Re-running on the same inputs produces the same id, so the
    # reflective tier can de-dupe — append-write is still safe because
    # an accept step reads the latest occurrence.
    id_seed = f"{signature.action_pattern}|{signature.domain}|{','.join(evidence_refs)}"
    # Use a crypto hash rather than Python's hash() because hash() is
    # randomized per process. Determinism is the contract.
    import hashlib
    proposal_id = "prop_" + hashlib.sha1(id_seed.encode("utf-8")).hexdigest()[:16]

    return {
        "id": proposal_id,
        "memory_class": "reflective",
        "kind": "semantic-promotion-proposal",
        "signature": signature.as_dict(),
        "sample_size": len(cluster),
        "observed_exits": with_exit,
        "observed_surfaces": with_surface,
        "success_rate": round(success_rate, 3),
        "stability": stability,
        "disconfirmation_fire_rate": (
            round(disc_rate, 3) if disc_rate is not None else None
        ),
        "proposed_semantic_entry": (
            f"Decisions matching `{signature.display()}` have observed "
            f"outcome `{stability}` over {len(cluster)} records "
            f"({round(success_rate * 100)}% success when exit was recorded). "
            f"Recommended: surface this pattern as a prior at Frame time "
            f"for future decisions with the same signature."
        ),
        "evidence_refs": evidence_refs,
        "status": "pending-review",
        "version": "memory-contract-v1",
    }


def build_proposals(
    records: Iterable[dict],
    *,
    min_cluster_size: int = DEFAULT_MIN_CLUSTER_SIZE,
) -> list[dict]:
    """Top-level: records → ranked proposal list. Only clusters of size
    >= min_cluster_size AND with at least one observed exit are
    considered. Proposals are sorted by (sample_size desc,
    action_pattern asc) so the output is deterministic.
    """
    groups = cluster_records(records)
    proposals: list[dict] = []
    for sig, cluster in groups.items():
        if len(cluster) < min_cluster_size:
            continue
        _, with_exit = _success_rate(cluster)
        if with_exit == 0:
            # A cluster with no observed outcomes is not a calibration
            # signal; don't surface as a proposal.
            continue
        proposals.append(analyze_cluster(sig, cluster))
    proposals.sort(
        key=lambda p: (-p["sample_size"], p["signature"]["action_pattern"])
    )
    return proposals


# ----- Reporting ------------------------------------------------------

def render_promotion_report(
    proposals: Sequence[dict],
    *,
    total_records: int,
    min_cluster_size: int,
) -> str:
    """Operator-facing Markdown summary. Matches the voice of
    `_render_friction_report` so the two analyzers feel like siblings
    rather than distinct tools.
    """
    lines: list[str] = []
    lines.append("# Semantic-Tier Promotion Report")
    lines.append("")
    lines.append(
        f"_Derived from {total_records} episodic records; "
        f"min cluster size {min_cluster_size}._"
    )
    lines.append("")

    if not proposals:
        lines.append("## No promotion candidates yet")
        lines.append("")
        lines.append(
            "Either there are not yet enough episodic records to form a "
            "stable cluster, or every cluster is under the minimum size. "
            "Keep operating; the episodic tier grows from high-impact "
            "actions with observed outcomes."
        )
        lines.append("")
        return "\n".join(lines)

    lines.append(f"## {len(proposals)} proposal(s)")
    lines.append("")
    lines.append(
        "These are **proposals**, not promotions. Nothing has been "
        "written to the semantic tier; all entries live under "
        "`~/.episteme/memory/reflective/semantic_proposals.jsonl` "
        "awaiting review."
    )
    lines.append("")

    for proposal in proposals:
        sig = proposal["signature"]
        lines.append(
            f"### `{sig['action_pattern']}` · domain={sig['domain']}"
        )
        lines.append("")
        lines.append(
            f"- **Sample size:** {proposal['sample_size']} "
            f"(observed exits: {proposal['observed_exits']}, "
            f"surfaces: {proposal['observed_surfaces']})"
        )
        lines.append(
            f"- **Success rate:** "
            f"{round(proposal['success_rate'] * 100)}% "
            f"(stability: `{proposal['stability']}`)"
        )
        disc = proposal["disconfirmation_fire_rate"]
        if disc is not None:
            lines.append(
                f"- **Disconfirmation fire rate (approx):** "
                f"{round(disc * 100)}%"
            )
        lines.append(f"- **Proposal id:** `{proposal['id']}`")
        lines.append("")
        lines.append(f"> {proposal['proposed_semantic_entry']}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "_Accept / decline: an explicit acceptance step is deferred to a "
        "later phase. Until then, these proposals inform the operator's "
        "own understanding of their decision patterns and feed the "
        "profile-audit loop (phase 12)._"
    )
    lines.append("")
    return "\n".join(lines)


# ----- Public entry point --------------------------------------------

def run_promote(
    *,
    episodic_dir: Path | None = None,
    reflective_dir: Path | None = None,
    output_path: Path | None = None,
    min_cluster_size: int = DEFAULT_MIN_CLUSTER_SIZE,
    now_iso: str | None = None,
) -> tuple[str, int, Path | None]:
    """Read episodic records, compute proposals, write to reflective tier,
    render a report. Returns (report_markdown, proposal_count,
    proposals_file_path_or_None).

    CLI wrapper prints the markdown and/or writes it to ``output_path``.
    """
    ed = episodic_dir or DEFAULT_EPISODIC_DIR
    rd = reflective_dir or DEFAULT_REFLECTIVE_DIR
    records = load_episodic_records(ed)
    proposals = build_proposals(records, min_cluster_size=min_cluster_size)
    written_to = write_proposals(proposals, rd, now_iso=now_iso)
    report = render_promotion_report(
        proposals, total_records=len(records), min_cluster_size=min_cluster_size
    )
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
    return report, len(proposals), written_to
