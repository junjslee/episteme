"""`episteme practice trace` — operator-facing PTSP trajectory recorder.

This module is the operator-facing surface for `core/ptsp/` — the
Provenance-Tagged Step Pipeline that counters the self-conditioning
effect documented in arXiv 2509.09677 ("prior LLM output silently
treated as fact in later steps; only provenance-typed context injection
fixes it").

Before this module, `core/ptsp/` was tested library code with no caller
in `src/episteme/` — the research-grounded machinery existed but was
unreachable. This wires it into a usable practice:

  episteme practice trace start    --session ID [--question ...]
  episteme practice trace fact     "<content>" --source LOCATOR --method M
  episteme practice trace infer    "<content>" [--confidence X] [--depends-on ID ...]
  episteme practice trace unknown  "<question>" --cost "<cost_of_ignorance>"
  episteme practice trace assume   "<assumption>" --if-wrong "..." --detectability D
  episteme practice trace promote  <inference-id> --test-id ID [--exit-code 0]
                                   <inference-id> --cosign
  episteme practice trace seal     [--session ID]
  episteme practice trace show     [--session ID]
  episteme practice trace status   [--session ID]

The point: an Inference cannot enter the Fact ledger without passing the
SAME tested promotion gate at `core/ptsp/promotion.py` —
operator cosign (Ed25519 over the inference content hash) or a
deterministic test pass. Inference-masquerading-as-fact across steps is
structurally blocked, which is exactly the arXiv 2509.09677 counter.

Storage (separate per-trace chain; does NOT touch
`.episteme/reasoning-surface.json` or the signed-surface chain):

  .episteme/traces/<session>/working.json     accumulating unsealed step
  .episteme/traces/<session>/step-0000.json   sealed StepBoundary JSON
  .episteme/traces/<session>/active.txt        active session pointer
"""
from __future__ import annotations

# pyright: reportMissingImports=false
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Event 172 — the installed entry point could not import `core.*`
# (repo-root package outside the installed tree), so this command
# CRASHED from the shipped CLI while the docs called it the operator's
# practice UX. Resolve the repo root from this file and put it on
# sys.path before the core imports; a no-op when already importable.
import sys as _sys
from pathlib import Path as _Path
_REPO_ROOT = _Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

from core.ptsp.types import (
    Assumption,
    Fact,
    Inference,
    ModelIdentity,
    OperatorCosign,
    PromotionRejected,
    SourceArtifact,
    StepBoundary,
    TestPassResult,
    Unknown,
)
from core.ptsp.promotion import promote_inference_to_fact
from core.ptsp.seal import seal_step_boundary
from core.ptsp.context_injection import render_step_context
from core.ptsp.canonical import jcs_canonical, sha256_hex
from episteme.surface._storage import episteme_root
from episteme import _ui


EXIT_OK = 0
EXIT_USAGE = 64
EXIT_NO_SESSION = 4
EXIT_PROMOTION_REJECTED = 5
EXIT_SEAL_REJECTED = 6


# ─── Storage ─────────────────────────────────────────────────────────────


def _traces_root(root: Optional[Path] = None) -> Path:
    return (root or episteme_root()) / "traces"


def _session_dir(session_id: str, *, root: Optional[Path] = None) -> Path:
    return _traces_root(root) / session_id


def _active_pointer(root: Optional[Path] = None) -> Path:
    return _traces_root(root) / "active.txt"


def _resolve_session(explicit: Optional[str], *, root: Optional[Path] = None) -> Optional[str]:
    if explicit:
        return explicit
    ptr = _active_pointer(root)
    if ptr.exists():
        return ptr.read_text(encoding="utf-8").strip() or None
    return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _operator_model_identity() -> ModelIdentity:
    """Inferences in a trace are the operator's provisional conjectures.

    The trace tool records the operator's own reasoning; an Inference is a
    claim not yet verified. generated_by is stamped 'operator-authored' so
    the provenance is honest — this is not an LLM completion.
    """
    return ModelIdentity(
        provider="operator",
        model_name="operator-authored",
        model_snapshot_hash="0" * 64,
        sampling_temperature=0.0,
        sampling_top_p=1.0,
    )


# ─── Working-step (unsealed) state ───────────────────────────────────────
#
# The working step accumulates ledger items before `seal`. It is a plain
# JSON envelope; on seal it is converted to typed objects and run through
# the tested seal_step_boundary, producing a sealed StepBoundary file.


def _empty_working(session_id: str, step_index: int, question: str) -> Dict[str, Any]:
    return {
        "session_id": session_id,
        "step_index": step_index,
        "core_question": question,
        "knowns": [],        # list of Fact.to_dict()
        "inferences": [],    # list of Inference.to_dict()
        "unknowns": [],      # list of Unknown.to_dict()
        "assumptions": [],   # list of Assumption.to_dict()
    }


def _working_path(session_id: str, *, root: Optional[Path] = None) -> Path:
    return _session_dir(session_id, root=root) / "working.json"


def _load_working(session_id: str, *, root: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    p = _working_path(session_id, root=root)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _save_working(session_id: str, working: Dict[str, Any], *, root: Optional[Path] = None) -> None:
    p = _working_path(session_id, root=root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(working, indent=2, sort_keys=True), encoding="utf-8")


def _sealed_steps(session_id: str, *, root: Optional[Path] = None) -> List[Dict[str, Any]]:
    sd = _session_dir(session_id, root=root)
    if not sd.exists():
        return []
    out = []
    for p in sorted(sd.glob("step-*.json")):
        out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


def _prior_sealed_boundary(session_id: str, *, root: Optional[Path] = None) -> Optional[StepBoundary]:
    """Reconstruct the most recent sealed StepBoundary (for parent_hash chaining)."""
    steps = _sealed_steps(session_id, root=root)
    if not steps:
        return None
    return _rehydrate_boundary(steps[-1])


# ─── Rehydration (dict → typed) ──────────────────────────────────────────


def _rehydrate_source_artifact(d: Dict[str, Any]) -> SourceArtifact:
    return SourceArtifact(type=d["type"], locator=d["locator"], content_hash=d["content_hash"])


def _rehydrate_fact(d: Dict[str, Any]) -> Fact:
    return Fact(
        content=d["content"],
        source_artifact=_rehydrate_source_artifact(d["source_artifact"]),
        verified_at=d["verified_at"],
        verification_method=d["verification_method"],
        created_at_step=d["created_at_step"],
        id=d["id"],
        depends_on=tuple(d.get("depends_on", [])),
    )


def _rehydrate_inference(d: Dict[str, Any]) -> Inference:
    g = d["generated_by"]
    return Inference(
        content=d["content"],
        generated_by=ModelIdentity(
            provider=g["provider"],
            model_name=g["model_name"],
            model_snapshot_hash=g["model_snapshot_hash"],
            sampling_temperature=g["sampling_temperature"],
            sampling_top_p=g["sampling_top_p"],
            sampling_seed=g.get("sampling_seed"),
        ),
        generated_at=d["generated_at"],
        created_at_step=d["created_at_step"],
        confidence_self_reported=d.get("confidence_self_reported", 0.0),
        id=d["id"],
        depends_on=tuple(d.get("depends_on", [])),
    )


def _rehydrate_unknown(d: Dict[str, Any]) -> Unknown:
    return Unknown(
        question=d["question"],
        cost_of_ignorance=d["cost_of_ignorance"],
        created_at_step=d["created_at_step"],
        id=d["id"],
        resolution_path=d.get("resolution_path"),
    )


def _rehydrate_assumption(d: Dict[str, Any]) -> Assumption:
    return Assumption(
        assumption=d["assumption"],
        if_wrong_then=d["if_wrong_then"],
        detectability=d["detectability"],
        created_at_step=d["created_at_step"],
        id=d["id"],
    )


def _rehydrate_boundary(d: Dict[str, Any]) -> StepBoundary:
    return StepBoundary(
        session_id=d["session_id"],
        step_index=d["step_index"],
        parent_hash=d.get("parent_hash"),
        knowns=tuple(_rehydrate_fact(x) for x in d.get("knowns", [])),
        inferences=tuple(_rehydrate_inference(x) for x in d.get("inferences", [])),
        unknowns=tuple(_rehydrate_unknown(x) for x in d.get("unknowns", [])),
        assumptions=tuple(_rehydrate_assumption(x) for x in d.get("assumptions", [])),
        model_calls=tuple(d.get("model_calls", [])),
        sealed_at=d["sealed_at"],
        self_hash=d["self_hash"],
        operator_signature=d.get("operator_signature"),
    )


# ─── Commands ────────────────────────────────────────────────────────────


def cmd_start(args: Any) -> int:
    session_id = args.session
    sd = _session_dir(session_id)
    if (sd / "working.json").exists() or list(sd.glob("step-*.json")):
        print(f"trace session '{session_id}' already exists; use a new --session id", file=sys.stderr)
        return EXIT_USAGE
    sd.mkdir(parents=True, exist_ok=True)
    working = _empty_working(session_id, 0, args.question or "")
    _save_working(session_id, working)
    _active_pointer().parent.mkdir(parents=True, exist_ok=True)
    _active_pointer().write_text(session_id, encoding="utf-8")
    print(f"trace started: session={session_id} step=0")
    if args.question:
        print(f"  core question: {args.question}")
    return EXIT_OK


def _require_working(args: Any) -> Optional[tuple[str, Dict[str, Any]]]:
    """Resolve (session_id, working) or None if unavailable.

    Returning a single Optional tuple (rather than a (None, None) pair) lets
    callers narrow both values with one `if result is None` guard.
    """
    session_id = _resolve_session(getattr(args, "session", None))
    if not session_id:
        print("no active trace session; run `episteme practice trace start --session ID`", file=sys.stderr)
        return None
    working = _load_working(session_id)
    if working is None:
        print(f"no working step for session '{session_id}'", file=sys.stderr)
        return None
    return session_id, working


def cmd_fact(args: Any) -> int:
    rw = _require_working(args)
    if rw is None:
        return EXIT_NO_SESSION
    session_id, working = rw
    fact = Fact(
        content=args.content,
        source_artifact=SourceArtifact(
            type=args.source_type, locator=args.source,
            content_hash=sha256_hex(args.content.encode("utf-8")),
        ),
        verified_at=_now(),
        verification_method=args.method,
        created_at_step=working["step_index"],
    )
    working["knowns"].append(fact.to_dict())
    _save_working(session_id, working)
    print(f"fact added: {fact.id}")
    return EXIT_OK


def cmd_infer(args: Any) -> int:
    rw = _require_working(args)
    if rw is None:
        return EXIT_NO_SESSION
    session_id, working = rw
    inf = Inference(
        content=args.content,
        generated_by=_operator_model_identity(),
        generated_at=_now(),
        created_at_step=working["step_index"],
        confidence_self_reported=args.confidence if args.confidence is not None else 0.0,
        depends_on=tuple(args.depends_on or ()),
    )
    working["inferences"].append(inf.to_dict())
    _save_working(session_id, working)
    print(f"inference added: {inf.id}  (NOT a fact until promoted with evidence)")
    return EXIT_OK


def cmd_unknown(args: Any) -> int:
    rw = _require_working(args)
    if rw is None:
        return EXIT_NO_SESSION
    session_id, working = rw
    u = Unknown(
        question=args.content,
        cost_of_ignorance=args.cost,
        created_at_step=working["step_index"],
    )
    working["unknowns"].append(u.to_dict())
    _save_working(session_id, working)
    print(f"unknown added: {u.id}")
    return EXIT_OK


def cmd_assume(args: Any) -> int:
    rw = _require_working(args)
    if rw is None:
        return EXIT_NO_SESSION
    session_id, working = rw
    a = Assumption(
        assumption=args.content,
        if_wrong_then=args.if_wrong,
        detectability=args.detectability,
        created_at_step=working["step_index"],
    )
    working["assumptions"].append(a.to_dict())
    _save_working(session_id, working)
    print(f"assumption added: {a.id}")
    return EXIT_OK


def cmd_promote(args: Any) -> int:
    rw = _require_working(args)
    if rw is None:
        return EXIT_NO_SESSION
    session_id, working = rw

    # Locate the target inference in the working step.
    inf_dict = next((i for i in working["inferences"] if i["id"] == args.inference_id), None)
    if inf_dict is None:
        print(f"inference '{args.inference_id}' not found in working step", file=sys.stderr)
        return EXIT_USAGE
    inference = _rehydrate_inference(inf_dict)

    ledger_facts = {f["id"]: _rehydrate_fact(f) for f in working["knowns"]}

    # Build evidence — TestPassResult (default) or OperatorCosign (--cosign).
    if args.cosign:
        kp = _read_operator_keypair()
        if kp is None:
            print("no operator keypair at .episteme/keys/; cannot cosign", file=sys.stderr)
            return EXIT_USAGE
        privkey, pubkey = kp
        cosigned_at = _now()
        payload = jcs_canonical({
            "inference_id": inference.id,
            "content_sha256": sha256_hex(inference.content.encode("utf-8")),
            "cosigned_at": cosigned_at,
        })
        from core.signing.ed25519_compat import sign_message
        sig = sign_message(privkey, payload)
        evidence: Any = OperatorCosign(
            operator_pubkey_hex=pubkey,
            signature_hex=sig,
            cosigned_at=cosigned_at,
        )
    else:
        if not args.test_id:
            print("promote requires either --cosign or --test-id <id>", file=sys.stderr)
            return EXIT_USAGE
        evidence = TestPassResult(
            test_id=args.test_id,
            test_target_inference_id=inference.id,
            test_command=args.test_command or args.test_id,
            exit_code=args.exit_code,
            stdout_sha256=sha256_hex((args.test_command or args.test_id).encode("utf-8")),
            ran_at=_now(),
        )

    try:
        new_fact = promote_inference_to_fact(
            inference, evidence, ledger_facts, working["step_index"],
        )
    except PromotionRejected as e:
        print(f"PROMOTION REJECTED [{e.code}]: {e.detail}", file=sys.stderr)
        print("  the inference stays an inference — the gate did its job.", file=sys.stderr)
        return EXIT_PROMOTION_REJECTED

    # Gate passed: move inference → fact in the working step.
    working["inferences"] = [i for i in working["inferences"] if i["id"] != args.inference_id]
    working["knowns"].append(new_fact.to_dict())
    _save_working(session_id, working)
    print(f"promoted: inference {args.inference_id} → fact {new_fact.id}")
    print(f"  via {new_fact.verification_method}")
    return EXIT_OK


def _read_operator_keypair():
    """Read .episteme/keys/operator_signing.{key,pub} authored by `surface`."""
    from episteme.surface._storage import read_keypair
    return read_keypair()


def cmd_seal(args: Any) -> int:
    rw = _require_working(args)
    if rw is None:
        return EXIT_NO_SESSION
    session_id, working = rw

    knowns = [_rehydrate_fact(x) for x in working["knowns"]]
    inferences = [_rehydrate_inference(x) for x in working["inferences"]]
    unknowns = [_rehydrate_unknown(x) for x in working["unknowns"]]
    assumptions = [_rehydrate_assumption(x) for x in working["assumptions"]]
    parent = _prior_sealed_boundary(session_id)

    try:
        boundary = seal_step_boundary(
            session_id=session_id,
            step_index=working["step_index"],
            parent_boundary=parent,
            knowns=knowns,
            inferences=inferences,
            unknowns=unknowns,
            assumptions=assumptions,
        )
    except Exception as e:
        print(f"SEAL REJECTED: {e}", file=sys.stderr)
        return EXIT_SEAL_REJECTED

    step_path = _session_dir(session_id) / f"step-{working['step_index']:04d}.json"
    step_path.write_text(json.dumps(boundary.to_full_dict(), indent=2, sort_keys=True), encoding="utf-8")

    # Advance: new empty working step, carrying knowns forward (Invariant I4
    # in seal_step_boundary requires parent KNOWNS ⊆ next KNOWNS).
    next_index = working["step_index"] + 1
    next_working = _empty_working(session_id, next_index, working.get("core_question", ""))
    next_working["knowns"] = [f.to_dict() for f in boundary.knowns]
    _save_working(session_id, next_working)

    print(f"sealed step {working['step_index']} → {step_path.name}")
    print(f"  self_hash: {boundary.self_hash[:16]}…")
    print(f"  advanced to step {next_index} (knowns carried forward: {len(boundary.knowns)})")
    return EXIT_OK


def cmd_show(args: Any) -> int:
    session_id = _resolve_session(getattr(args, "session", None))
    if not session_id:
        print("no active trace session", file=sys.stderr)
        return EXIT_NO_SESSION
    sealed = _sealed_steps(session_id)
    print(_ui.header(f"Trace · {session_id}", level=1, color="cyan"))
    print()
    for d in sealed:
        boundary = _rehydrate_boundary(d)
        print(render_step_context(boundary))
        print()
    working = _load_working(session_id)
    if working and (working["knowns"] or working["inferences"]
                    or working["unknowns"] or working["assumptions"]):
        print(_ui.header(f"Working step {working['step_index']} (unsealed)", level=2, color="yellow"))
        print(_ui.colored(
            f"  facts={len(working['knowns'])}  inferences={len(working['inferences'])}  "
            f"unknowns={len(working['unknowns'])}  assumptions={len(working['assumptions'])}",
            "grey",
        ))
        for i in working["inferences"]:
            print(_ui.colored(f"  inference {i['id']}: {i['content'][:70]}", "grey"))
    return EXIT_OK


def cmd_status(args: Any) -> int:
    session_id = _resolve_session(getattr(args, "session", None))
    if not session_id:
        if args.format == "json":
            print(json.dumps({"active": None}))
        else:
            print("active trace: (none)")
        return EXIT_OK
    sealed = _sealed_steps(session_id)
    working = _load_working(session_id) or {}
    info = {
        "session": session_id,
        "sealed_steps": len(sealed),
        "working_step_index": working.get("step_index"),
        "working_facts": len(working.get("knowns", [])),
        "working_inferences": len(working.get("inferences", [])),
        "working_unknowns": len(working.get("unknowns", [])),
        "working_assumptions": len(working.get("assumptions", [])),
        "head_self_hash": sealed[-1]["self_hash"] if sealed else None,
    }
    if args.format == "json":
        print(json.dumps(info, indent=2))
    else:
        print(_ui.header(f"Trace status · {session_id}", level=2, color="cyan"))
        for k, v in info.items():
            print(f"  {k:<22} {v}")
    return EXIT_OK


# ─── Dispatch ────────────────────────────────────────────────────────────


def run_trace(args: Any) -> int:
    action = getattr(args, "trace_action", None) or ""
    handlers = {
        "start": cmd_start,
        "fact": cmd_fact,
        "infer": cmd_infer,
        "unknown": cmd_unknown,
        "assume": cmd_assume,
        "promote": cmd_promote,
        "seal": cmd_seal,
        "show": cmd_show,
        "status": cmd_status,
    }
    h = handlers.get(action)
    if not h:
        print("usage: episteme practice trace {start|fact|infer|unknown|assume|promote|seal|show|status}", file=sys.stderr)
        return EXIT_USAGE
    return h(args)


def add_trace_subparser(sub) -> None:
    """Register `trace` under the practice subparser. Called by _cli.build_parser."""
    trace = sub.add_parser("trace", help="Record a PTSP reasoning trajectory (Fact/Inference typed, gate-enforced)")
    tsub = trace.add_subparsers(dest="trace_action", required=True)

    p = tsub.add_parser("start", help="Start a new trace session")
    p.add_argument("--session", required=True)
    p.add_argument("--question", default="")

    p = tsub.add_parser("fact", help="Add a verified Fact to the working step")
    p.add_argument("content")
    p.add_argument("--source", required=True, help="source artifact locator")
    p.add_argument("--source-type", default="operator_attestation",
                   choices=["path", "url", "commit_sha", "test_id", "oracle_id", "operator_attestation"])
    p.add_argument("--method", default="operator_read",
                   choices=["operator_cosign", "test_pass", "external_oracle", "operator_read", "original_axiom"])
    p.add_argument("--session")

    p = tsub.add_parser("infer", help="Add an Inference (NOT a fact until promoted)")
    p.add_argument("content")
    p.add_argument("--confidence", type=float, default=None)
    p.add_argument("--depends-on", nargs="*", default=[])
    p.add_argument("--session")

    p = tsub.add_parser("unknown", help="Register an Unknown with cost_of_ignorance")
    p.add_argument("content")
    p.add_argument("--cost", required=True, help="cost_of_ignorance")
    p.add_argument("--session")

    p = tsub.add_parser("assume", help="Register an Assumption with if_wrong_then + detectability")
    p.add_argument("content")
    p.add_argument("--if-wrong", required=True, dest="if_wrong")
    p.add_argument("--detectability", default="post_execution_soft",
                   choices=["pre_execution", "post_execution_soft", "post_execution_irreversible"])
    p.add_argument("--session")

    p = tsub.add_parser("promote", help="Promote an Inference → Fact through the PTSP gate")
    p.add_argument("inference_id")
    p.add_argument("--test-id", default=None, help="evidence: deterministic test id")
    p.add_argument("--test-command", default=None)
    p.add_argument("--exit-code", type=int, default=0)
    p.add_argument("--cosign", action="store_true", help="evidence: operator Ed25519 cosign via .episteme/keys/")
    p.add_argument("--session")

    p = tsub.add_parser("seal", help="Seal the working step (hash-chained) and advance")
    p.add_argument("--session")

    p = tsub.add_parser("show", help="Render the trajectory with typed <fact>/<inference> tags")
    p.add_argument("--session")

    p = tsub.add_parser("status", help="Trace status summary")
    p.add_argument("--session")
    p.add_argument("--format", choices=("human", "json"), default="human")
