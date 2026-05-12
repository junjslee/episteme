"""argparse glue for `episteme surface ...` subcommands.

This module is the operator-facing entrypoint. Every subcommand exits with a
deterministic exit code so scripts can chain it cleanly:

  0   success
  2   validation error (lazy placeholder, missing field, short content)
  3   signing error (key missing, signature failed)
  4   surface not found
  5   active-surface unset
  10  signature invalid on verify-active
  64  usage error
"""
from __future__ import annotations

# pyright: reportMissingImports=false
import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.ptsp.canonical import sha256_hex, sha256_of_jcs
from core.signing import (
    SurfaceVerificationError,
    generate_keypair,
    is_production_grade,
    mock_tsa_token,
    sign_surface,
    signature_mode,
    verify_surface,
)
from core.signing.transparency import build_inclusion_proof_shape, verify_inclusion_proof_shape
from core.signing.tsa import verify_tsa_token

from episteme.surface._builder import (
    new_surface_skeleton,
    validate_surface_body,
)
from episteme.surface._storage import (
    ensure_storage,
    find_surface,
    get_active_surface_id,
    get_active_surface_path,
    iter_surfaces,
    read_keypair,
    read_public_key_by_fingerprint,
    set_active_surface,
    write_keypair,
    write_surface,
)


# ─── Exit codes ──────────────────────────────────────────────────────────

EXIT_OK = 0
EXIT_VALIDATION = 2
EXIT_SIGNING = 3
EXIT_NOT_FOUND = 4
EXIT_NO_ACTIVE = 5
EXIT_SIG_INVALID = 10
EXIT_USAGE = 64


# ─── Helpers ─────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _new_surface_id() -> str:
    """ULID-shaped id (timestamp prefix + uuid suffix) for sortable file names."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"surf-{ts}-{uuid.uuid4().hex[:8]}"


def _ensure_keys() -> tuple[str, str]:
    """Read existing keypair or generate-and-write a new one."""
    existing = read_keypair()
    if existing:
        return existing
    privkey, pubkey = generate_keypair()
    write_keypair(privkey, pubkey)
    return privkey, pubkey


def _load_body_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    """Build the surface body from --body-file or --field args, with sensible
    defaults from the skeleton."""
    body = new_surface_skeleton()
    if getattr(args, "body_file", None):
        with open(args.body_file, encoding="utf-8") as f:
            loaded = json.load(f)
        # Merge: loaded fields override skeleton fields
        body.update(loaded)
    if getattr(args, "core_question", None):
        body["core_question"] = args.core_question
    if getattr(args, "decision_choice", None):
        body["decision"]["choice"] = args.decision_choice
    if getattr(args, "decision_confidence", None) is not None:
        body["decision"]["confidence"] = args.decision_confidence
    if getattr(args, "stop_rollback_path", None):
        body["decision"]["stop_rollback_path"] = args.stop_rollback_path
    if getattr(args, "blueprint", None):
        body["audit"]["blueprint_invoked"] = args.blueprint
    if getattr(args, "reversibility", None):
        body["risk_classification"]["reversibility"] = args.reversibility
    if getattr(args, "blast_radius", None):
        body["risk_classification"]["blast_radius"] = args.blast_radius
    if getattr(args, "ai_act_tier", None):
        body["risk_classification"]["ai_act_tier"] = args.ai_act_tier
    return body


def _print_validation_errors(errors: List[str]) -> None:
    print("validation failed:", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)


# ─── Subcommand: author ──────────────────────────────────────────────────


def cmd_author(args: argparse.Namespace) -> int:
    """Interactive or non-interactive author flow.

    Non-interactive: supply --body-file pointing to a JSON file with the
    surface body. Required fields can be overridden by --core-question,
    --decision-choice, etc.

    Interactive: prompts for each required field.
    """
    ensure_storage()
    privkey, pubkey = _ensure_keys()

    if args.interactive:
        body = _author_interactive()
    else:
        body = _load_body_from_args(args)

    errors = validate_surface_body(body)
    if errors:
        _print_validation_errors(errors)
        return EXIT_VALIDATION

    return _sign_and_persist(
        body=body,
        privkey=privkey,
        pubkey=pubkey,
        with_tsa=args.with_tsa,
        with_rekor=args.with_rekor,
        set_active=args.set_active,
        format_=args.format,
    )


def _author_interactive() -> Dict[str, Any]:
    """Stdin-prompt loop with cognitive-move-name preambles.

    Each prompt is preceded by:
      - the cognitive move it represents (name + description)
      - the named System-1 failure mode it counters
    The visual rendering falls back to plain ASCII on non-TTY / NO_COLOR
    via the _ui module's auto-detection. Empty input falls back to defaults
    where they exist; required fields are validated downstream.
    """
    from episteme import _ui
    from core.practice.cognitive_moves import get_move, ordered_stages

    body = new_surface_skeleton()

    print()
    print(_ui.header("episteme · Reasoning Surface · interactive author", level=1, color="cyan"))
    print()
    print("Each prompt below corresponds to a cognitive move in the practice.")
    print(_ui.colored("See `episteme practice walk` for the full 5-stage walkthrough.", "grey"))
    print(_ui.colored("Press Ctrl-C to abort at any time.", "grey"))
    print()

    def _prompt_for_move(move_id: str, prompt_text: str, *, multiline_hint: str = "") -> str:
        """Render move-name preamble, then prompt and return stripped input."""
        try:
            move = get_move(move_id)
            print(_ui.colored(f"  Move: {move.name}", "bold"))
            print(_ui.colored(f"  Counters: {move.system_1_failure_counter}", "grey"))
        except KeyError:
            pass
        if multiline_hint:
            print(_ui.colored(f"  {multiline_hint}", "grey"))
        try:
            value = input(f"  → {prompt_text}").strip()
        except EOFError:
            value = ""
        print()
        return value

    # ── Stage 1: Frame ──
    stages = {s.id: s for s in ordered_stages()}
    print(_ui.header("Stage 1/5 · Frame", level=2, color="cyan"))
    print(_ui.colored(stages["frame"].purpose, "grey"))
    print()

    body["core_question"] = _prompt_for_move(
        "frame.core_question",
        "Core question (≥20 chars): ",
    )
    rev = _prompt_for_move(
        "frame.reversibility",
        "Reversibility [reversible|irreversible] (default: irreversible): ",
    )
    if rev:
        body["risk_classification"]["reversibility"] = rev
    blast = _prompt_for_move(
        "frame.constraint_regime",
        "Blast radius [local|repo|external_service|user_visible|regulated_artifact] (default: repo): ",
    )
    if blast:
        body["risk_classification"]["blast_radius"] = blast
    tier = _prompt_for_move(
        "frame.constraint_regime",
        "AI Act tier [minimal|limited|high|unacceptable] (default: limited): ",
    )
    if tier:
        body["risk_classification"]["ai_act_tier"] = tier

    # ── Unknowns ──
    print(_ui.header("Unknowns (Frame · WYSIATI counter)", level=2, color="cyan"))
    print(_ui.colored("Each unknown needs a real cost_of_ignorance (≥30 chars).", "grey"))
    print()
    u_q = _prompt_for_move("frame.unknowns", "unknown: ")
    if u_q:
        u_w = input("  → why_not_resolvable_now: ").strip()
        u_c = input("  → cost_of_ignorance (≥30 chars): ").strip()
        body["unknowns"].append({
            "unknown": u_q,
            "why_not_resolvable_now": u_w,
            "cost_of_ignorance": u_c,
        })
    print()

    # ── Assumptions ──
    print(_ui.header("Assumptions (Frame · overconfidence counter)", level=2, color="cyan"))
    print()
    a = _prompt_for_move("frame.assumptions", "assumption: ")
    if a:
        aw = input("  → if_wrong_then: ").strip()
        det = input("  → detectability [pre_execution|post_execution_soft|post_execution_irreversible]: ").strip()
        body["assumptions"].append({
            "assumption": a, "if_wrong_then": aw, "detectability": det or "post_execution_soft",
        })
    print()

    # ── Disconfirmation ──
    print(_ui.header("Disconfirmation (Verify · robust falsifiability)", level=2, color="cyan"))
    print(_ui.colored("Pre-committed observable that would invalidate the plan.", "grey"))
    print()
    obs = _prompt_for_move("verify.disconfirmation_conditions", "observable: ")
    if obs:
        meth = input("  → measurement_method: ").strip()
        body["disconfirmation_conditions"].append({
            "observable": obs, "measurement_method": meth, "would_invalidate_plan": True,
        })
    print()

    # ── Decision (Decompose hypothesis-as-bet + Handoff rollback) ──
    print(_ui.header("Decision (Decompose · hypothesis-as-bet + Handoff · rollback)", level=2, color="cyan"))
    print()
    body["decision"]["choice"] = _prompt_for_move(
        "decompose.hypothesis_as_bet",
        "choice [proceed|stop|audit]: ",
    ) or "proceed"
    conf_str = _prompt_for_move(
        "decompose.hypothesis_as_bet",
        "confidence [0.0-1.0]: ",
    )
    try:
        body["decision"]["confidence"] = float(conf_str) if conf_str else 0.0
    except ValueError:
        body["decision"]["confidence"] = 0.0
    body["decision"]["stop_rollback_path"] = _prompt_for_move(
        "handoff.stop_rollback_path",
        "stop_rollback_path (≥10 chars, concrete steps to undo): ",
    )

    bp = _prompt_for_move(
        "frame.core_question",
        "blueprint_invoked [consequence_chain|axiomatic_judgment|fence_reconstruction|architectural_cascade] (default: consequence_chain): ",
    )
    if bp:
        body["audit"]["blueprint_invoked"] = bp

    # Brief practice-quality preview before signing
    try:
        from core.practice.quality import observe_surface
        # Wrap in minimal envelope so observe_surface can read it
        observation_input = {"envelope": {}, "surface": body}
        obs_list = observe_surface(observation_input)
        if obs_list:
            print(_ui.divider())
            print()
            print(_ui.header("Practice-quality preview", level=2, color="yellow"))
            print(_ui.colored("These observations will surface in `episteme practice retro`.", "grey"))
            print(_ui.colored("They do not block signing — but they name where the practice was shallow.", "grey"))
            print()
            from episteme._ui import Color as _UiColor
            from typing import cast as _cast
            _sev_colors: Dict[str, _UiColor] = {
                "critical": "red", "warn": "yellow", "advisory": "grey", "info": "grey",
            }
            for o in obs_list[:8]:
                severity_color = _sev_colors.get(o.severity, _cast(_UiColor, "grey"))
                tag = _ui.colored(f"[{o.severity.upper()}]", severity_color)
                print(f"  {tag} {o.summary}")
            print()
    except Exception:
        # Practice-quality preview is best-effort; don't break the author flow.
        pass

    return body


def _sign_and_persist(
    *,
    body: Dict[str, Any],
    privkey: str,
    pubkey: str,
    with_tsa: bool,
    with_rekor: bool,
    set_active: bool,
    format_: str,
) -> int:
    sid = _new_surface_id()
    session_id = body.get("_session_id", "session-default")

    # Build TSA + Rekor shapes BEFORE signing so the payload hash matches.
    issued_at = _now_iso()
    envelope_for_hash = {
        "schema_version": "signed-surface@1.0",
        "surface_id": sid,
        "session_id": session_id,
        "operator_pubkey_fingerprint": sha256_hex(bytes.fromhex(pubkey)),
        "parent_surface_hash": None,
        "issued_at": issued_at,
    }
    payload_hash = sha256_of_jcs({"envelope": envelope_for_hash, "surface": body})
    tsa_token = mock_tsa_token(payload_hash) if with_tsa else None
    rekor_proof = build_inclusion_proof_shape(payload_hash, log_index=0) if with_rekor else None

    try:
        signed = sign_surface(
            surface=body,
            private_key_hex=privkey,
            public_key_hex=pubkey,
            surface_id=sid,
            session_id=session_id,
            issued_at=issued_at,
            tsa_token=tsa_token,
            rekor_inclusion_proof=rekor_proof,
        )
    except Exception as e:
        print(f"sign failed: {e}", file=sys.stderr)
        return EXIT_SIGNING

    path = write_surface(sid, signed.to_dict())
    if set_active:
        set_active_surface(sid)

    if format_ == "json":
        print(json.dumps({
            "surface_id": sid,
            "path": str(path),
            "signature_mode": signature_mode(signed.attestation["signature_b64_or_hex"]),
            "production_grade_signing": is_production_grade(),
            "set_active": set_active,
        }, indent=2))
    else:
        print(f"signed: {sid}")
        print(f"  path:               {path}")
        print(f"  signature mode:     {signature_mode(signed.attestation['signature_b64_or_hex'])}")
        print(f"  production-grade:   {is_production_grade()}")
        print(f"  active:             {set_active}")
        if not is_production_grade():
            print("\n  WARNING: PyNaCl not installed; signature is HMAC-SHA256 (test mode).")
            print("           Install with: pip install episteme[signing]")
            print("           Auditors will reject test-mode signatures by default.")
    return EXIT_OK


# ─── Subcommand: sign ────────────────────────────────────────────────────


def cmd_sign(args: argparse.Namespace) -> int:
    """Sign a draft surface body (JSON file) and persist it."""
    ensure_storage()
    privkey, pubkey = _ensure_keys()
    try:
        with open(args.body_file, encoding="utf-8") as f:
            body = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"could not read body file: {e}", file=sys.stderr)
        return EXIT_VALIDATION
    errors = validate_surface_body(body)
    if errors:
        _print_validation_errors(errors)
        return EXIT_VALIDATION
    return _sign_and_persist(
        body=body,
        privkey=privkey,
        pubkey=pubkey,
        with_tsa=args.with_tsa,
        with_rekor=args.with_rekor,
        set_active=args.set_active,
        format_=args.format,
    )


# ─── Subcommand: show ────────────────────────────────────────────────────


def cmd_show(args: argparse.Namespace) -> int:
    """Show a surface by id, or the active surface if none given."""
    if args.surface_id:
        path = find_surface(args.surface_id)
        if not path:
            print(f"surface not found: {args.surface_id}", file=sys.stderr)
            return EXIT_NOT_FOUND
    else:
        path = get_active_surface_path()
        if not path:
            print("no active surface set; pass <surface_id> or run `surface author`", file=sys.stderr)
            return EXIT_NO_ACTIVE

    data = json.loads(path.read_text(encoding="utf-8"))
    if args.format == "json":
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        env = data.get("envelope", {})
        surf = data.get("surface", {})
        att = data.get("attestation", {})
        print(f"surface_id:      {env.get('surface_id')}")
        print(f"session:         {env.get('session_id')}")
        print(f"signed at:       {att.get('signed_at')}")
        print(f"signature mode:  {signature_mode(att.get('signature_b64_or_hex', ''))}")
        print(f"core question:   {surf.get('core_question', '')}")
        rc = surf.get("risk_classification", {})
        print(f"risk:            {rc.get('reversibility')} / {rc.get('blast_radius')} / {rc.get('ai_act_tier')}")
        dec = surf.get("decision", {})
        print(f"decision:        {dec.get('choice')} (confidence {dec.get('confidence')})")
        print(f"unknowns:        {len(surf.get('unknowns', []))}")
        print(f"assumptions:     {len(surf.get('assumptions', []))}")
        print(f"disconfirm.:     {len(surf.get('disconfirmation_conditions', []))}")
        print(f"file:            {path}")
    return EXIT_OK


# ─── Subcommand: list ────────────────────────────────────────────────────


def cmd_list(args: argparse.Namespace) -> int:
    """List signed surfaces newest-first."""
    rows = []
    for path in iter_surfaces():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        env = data.get("envelope", {})
        surf = data.get("surface", {})
        rows.append({
            "surface_id": env.get("surface_id"),
            "issued_at": env.get("issued_at"),
            "tier": surf.get("risk_classification", {}).get("ai_act_tier"),
            "reversibility": surf.get("risk_classification", {}).get("reversibility"),
            "choice": surf.get("decision", {}).get("choice"),
            "path": str(path),
        })
        if args.limit and len(rows) >= args.limit:
            break

    active_id = get_active_surface_id()
    if args.format == "json":
        print(json.dumps({"active_surface_id": active_id, "surfaces": rows}, indent=2))
    else:
        if not rows:
            print("(no surfaces)")
            return EXIT_OK
        print(f"active: {active_id or '(none)'}")
        print(f"{'surface_id':<32} {'issued_at':<28} {'tier':<10} {'reversibility':<14} {'choice':<8}")
        for r in rows:
            marker = "*" if r["surface_id"] == active_id else " "
            print(f"{marker}{r['surface_id']:<31} {r['issued_at']:<28} {r['tier'] or '':<10} "
                  f"{r['reversibility'] or '':<14} {r['choice'] or '':<8}")
    return EXIT_OK


# ─── Subcommand: status ──────────────────────────────────────────────────


def cmd_status(args: argparse.Namespace) -> int:
    """Brief one-screen status of the active surface (for shell prompts)."""
    active_id = get_active_surface_id()
    if not active_id:
        if args.format == "json":
            print(json.dumps({"active": None}))
        else:
            print("active: (none)")
        return EXIT_OK
    path = get_active_surface_path()
    if not path:
        print(f"active surface id set to {active_id} but file not found", file=sys.stderr)
        return EXIT_NOT_FOUND
    data = json.loads(path.read_text(encoding="utf-8"))
    att = data.get("attestation", {})
    surf = data.get("surface", {})
    info = {
        "active": active_id,
        "signed_at": att.get("signed_at"),
        "signature_mode": signature_mode(att.get("signature_b64_or_hex", "")),
        "reversibility": surf.get("risk_classification", {}).get("reversibility"),
        "ai_act_tier": surf.get("risk_classification", {}).get("ai_act_tier"),
        "decision": surf.get("decision", {}).get("choice"),
    }
    if args.format == "json":
        print(json.dumps(info))
    else:
        print(f"active:          {info['active']}")
        print(f"signed_at:       {info['signed_at']}")
        print(f"sig mode:        {info['signature_mode']}")
        print(f"reversibility:   {info['reversibility']}")
        print(f"ai_act_tier:     {info['ai_act_tier']}")
        print(f"decision:        {info['decision']}")
    return EXIT_OK


# ─── Subcommand: verify (active surface) ─────────────────────────────────


def cmd_verify_active(args: argparse.Namespace) -> int:
    """Run the standalone verifier against the active surface."""
    path = get_active_surface_path()
    if not path:
        print("no active surface", file=sys.stderr)
        return EXIT_NO_ACTIVE
    data = json.loads(path.read_text(encoding="utf-8"))

    def resolver(fp: str) -> str:
        pk = read_public_key_by_fingerprint(fp)
        if pk is None:
            raise FileNotFoundError(f"no pubkey for fingerprint {fp}")
        return pk

    try:
        verify_surface(
            data,
            public_key_resolver=resolver,
            allow_test_signatures=args.allow_test_signatures,
            verify_tsa_fn=verify_tsa_token if args.verify_tsa else None,
            verify_rekor_fn=verify_inclusion_proof_shape if args.verify_rekor else None,
        )
    except SurfaceVerificationError as e:
        if args.format == "json":
            print(json.dumps({"ok": False, "exit_code": e.exit_code, "code": e.code, "detail": e.detail}))
        else:
            print(f"verify FAIL [{e.exit_code}] {e.code}: {e.detail}", file=sys.stderr)
        return e.exit_code
    if args.format == "json":
        print(json.dumps({"ok": True}))
    else:
        print(f"verify OK: {path}")
    return EXIT_OK


# ─── argparse ────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="episteme surface",
        description="Author, sign, and manage Signed Reasoning Surfaces.",
    )
    sub = p.add_subparsers(dest="action", required=True)

    # author
    author = sub.add_parser("author", help="Author + sign a new Reasoning Surface")
    author.add_argument("--interactive", "-i", action="store_true", help="Prompt for fields interactively")
    author.add_argument("--body-file", help="JSON file with surface body (non-interactive)")
    author.add_argument("--core-question", help="Override core_question")
    author.add_argument("--decision-choice", choices=("proceed", "stop", "audit"))
    author.add_argument("--decision-confidence", type=float)
    author.add_argument("--stop-rollback-path", help="Decision rollback path")
    author.add_argument("--blueprint")
    author.add_argument("--reversibility")
    author.add_argument("--blast-radius")
    author.add_argument("--ai-act-tier")
    author.add_argument("--with-tsa", action="store_true", help="Attach mock RFC 3161 TSA token")
    author.add_argument("--with-rekor", action="store_true", help="Attach mock Sigstore Rekor inclusion proof")
    author.add_argument("--set-active", action="store_true", default=True, help="Set as active (default)")
    author.add_argument("--no-set-active", dest="set_active", action="store_false")
    author.add_argument("--format", choices=("human", "json"), default="human")

    # sign
    sign = sub.add_parser("sign", help="Sign a draft surface body (JSON file)")
    sign.add_argument("body_file", help="Path to surface body JSON")
    sign.add_argument("--with-tsa", action="store_true")
    sign.add_argument("--with-rekor", action="store_true")
    sign.add_argument("--set-active", action="store_true", default=True)
    sign.add_argument("--no-set-active", dest="set_active", action="store_false")
    sign.add_argument("--format", choices=("human", "json"), default="human")

    # show
    show = sub.add_parser("show", help="Show a surface")
    show.add_argument("surface_id", nargs="?", help="Surface id (default: active)")
    show.add_argument("--format", choices=("human", "json"), default="human")

    # list
    lst = sub.add_parser("list", help="List signed surfaces newest-first")
    lst.add_argument("--limit", type=int, default=20)
    lst.add_argument("--format", choices=("human", "json"), default="human")

    # status
    status = sub.add_parser("status", help="Brief active-surface status")
    status.add_argument("--format", choices=("human", "json"), default="human")

    # verify-active
    verify = sub.add_parser("verify", help="Verify the active surface")
    verify.add_argument("--allow-test-signatures", action="store_true")
    verify.add_argument("--verify-tsa", action="store_true")
    verify.add_argument("--verify-rekor", action="store_true")
    verify.add_argument("--format", choices=("human", "json"), default="human")

    return p


def run_surface_cli(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "author": cmd_author,
        "sign": cmd_sign,
        "show": cmd_show,
        "list": cmd_list,
        "status": cmd_status,
        "verify": cmd_verify_active,
    }
    handler = handlers.get(args.action)
    if not handler:
        parser.print_help(sys.stderr)
        return EXIT_USAGE
    return handler(args)


def main(argv: Optional[List[str]] = None) -> int:
    return run_surface_cli(argv)


if __name__ == "__main__":
    sys.exit(main())
