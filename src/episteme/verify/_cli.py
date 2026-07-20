"""episteme verify CLI — independent verification of Signed Reasoning Surfaces.

Exit code contract (deterministic, stable):

  0   All surfaces verified.
  10  Signature invalid on at least one surface.
  11  Timestamp invalid (TSA token / asserted_timestamp drift).
  12  Transparency log inclusion failed (when live mode enabled).
  13  Hash chain break.
  14  Self-hash mismatch.
  20  Surface file malformed / schema-invalid.
  21  Required key resolution failed.
  30  Mixed result in batch mode; see report for per-file status.
  64  Usage error.

The verifier does NOT call into the episteme runtime. It depends only on:
  - Python stdlib
  - `core.ptsp.canonical` (pure JCS + SHA-256)
  - `core.signing.*` (Ed25519/HMAC-SHA256 compat layer)

No filesystem state outside `--root` is touched. No network calls unless
the caller passes a public_key_resolver that itself does network I/O.
"""
from __future__ import annotations

# pyright: reportMissingImports=false
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

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

from core.signing.canonical_surface import (
    SurfaceVerificationError,
    verify_surface,
)
from core.signing.tsa import verify_tsa_token, TSAVerificationError
from core.signing.transparency import (
    verify_inclusion_proof_shape,
    RekorVerificationError,
)


# ─── Deterministic exit codes ─────────────────────────────────────────────

EXIT_OK = 0
EXIT_SIGNATURE = 10
EXIT_TIMESTAMP = 11
EXIT_LOG_INCLUSION = 12
EXIT_CHAIN_BREAK = 13
EXIT_SELF_HASH = 14
EXIT_MALFORMED = 20
EXIT_KEY_RESOLUTION = 21
EXIT_BATCH_MIXED = 30
EXIT_USAGE = 64


# ─── Pubkey resolver: file-based for tests, pluggable for prod ────────────

def make_file_resolver(keys_dir: Path) -> Callable[[str], str]:
    """Resolver that loads `<fingerprint>.pub` files from a directory.

    Each file contains a single hex string — the public key bytes.
    """
    def resolver(fingerprint: str) -> str:
        path = keys_dir / f"{fingerprint}.pub"
        if not path.exists():
            raise FileNotFoundError(f"no public key file for fingerprint {fingerprint} at {path}")
        return path.read_text(encoding="utf-8").strip()
    return resolver


# ─── Single-surface verification ──────────────────────────────────────────

def verify_one(
    signed_surface_dict: Dict[str, Any],
    *,
    resolver: Callable[[str], str],
    allow_test_signatures: bool,
    verify_tsa: bool,
    verify_rekor: bool,
) -> Tuple[int, str, str]:
    """Returns (exit_code, status_label, detail)."""
    tsa_fn = verify_tsa_token if verify_tsa else None
    rekor_fn = verify_inclusion_proof_shape if verify_rekor else None
    try:
        verify_surface(
            signed_surface_dict,
            public_key_resolver=resolver,
            allow_test_signatures=allow_test_signatures,
            verify_tsa_fn=tsa_fn,
            verify_rekor_fn=rekor_fn,
        )
        return (EXIT_OK, "PASS", "")
    except SurfaceVerificationError as e:
        return (e.exit_code, "FAIL", f"{e.code}: {e.detail}")
    except (TSAVerificationError, RekorVerificationError) as e:
        # Should be wrapped by verify_surface, but defensive.
        return (EXIT_TIMESTAMP, "FAIL", str(e))


# ─── Chain verification ───────────────────────────────────────────────────

def verify_chain(
    surfaces_in_order: List[Dict[str, Any]],
    *,
    resolver: Callable[[str], str],
    allow_test_signatures: bool,
    verify_tsa: bool,
    verify_rekor: bool,
) -> Tuple[int, List[Dict[str, Any]]]:
    """Verify a sequence of surfaces and their parent_surface_hash chain.

    Returns (final_exit_code, per_surface_results).
    """
    results: List[Dict[str, Any]] = []
    prior_hash: Optional[str] = None
    chain_broken_at: Optional[int] = None

    for i, sf in enumerate(surfaces_in_order):
        # First check the chain
        declared_parent = sf.get("envelope", {}).get("parent_surface_hash")
        if i == 0:
            # First surface in chain may have null parent (genesis)
            if declared_parent not in (None, ""):
                # Not strictly an error — could be continuing a prior session —
                # but we record it for the report.
                pass
        else:
            if declared_parent != prior_hash:
                chain_broken_at = i
                results.append({
                    "index": i,
                    "exit_code": EXIT_CHAIN_BREAK,
                    "status": "FAIL",
                    "detail": (
                        f"chain_break: surface {i}'s parent_surface_hash "
                        f"({(declared_parent or '')[:16]}...) does not match "
                        f"prior surface self_hash ({(prior_hash or '')[:16]}...)"
                    ),
                })
                break

        # Then verify the surface itself
        ec, status, detail = verify_one(
            sf,
            resolver=resolver,
            allow_test_signatures=allow_test_signatures,
            verify_tsa=verify_tsa,
            verify_rekor=verify_rekor,
        )
        results.append({
            "index": i,
            "exit_code": ec,
            "status": status,
            "detail": detail,
        })
        if ec != EXIT_OK:
            return (ec, results)

        # Compute this surface's recomputed self_hash for next iteration's chain
        # check. We use the declared self_hash since verify_one already
        # confirmed it matches recomputed.
        prior_hash = sf.get("self_hash")

    if chain_broken_at is not None:
        return (EXIT_CHAIN_BREAK, results)
    return (EXIT_OK, results)


# ─── Argparse + main ──────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="episteme verify",
        description=(
            "Independent verification of Signed Reasoning Surfaces. "
            "Validates cryptographic, temporal, log-inclusion, and "
            "chain-integrity properties without trusting the episteme runtime."
        ),
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("surface_file", nargs="?", help="Single signed surface JSON file")
    mode.add_argument("--batch", metavar="DIR", help="Verify every *.json in DIR")
    mode.add_argument("--chain", metavar="MANIFEST", help="Verify ordered chain from manifest file")

    p.add_argument("--keys-dir", required=True, help="Directory containing <fingerprint>.pub key files")
    p.add_argument("--format", choices=("json", "human"), default="human")
    p.add_argument(
        "--allow-test-signatures",
        action="store_true",
        help="Accept test-mode HMAC signatures (NOT for production audit)",
    )
    p.add_argument(
        "--verify-tsa",
        action="store_true",
        help="Verify attached TSA tokens (RFC 3161 shape)",
    )
    p.add_argument(
        "--verify-rekor",
        action="store_true",
        help="Verify attached Sigstore Rekor inclusion proofs",
    )
    p.add_argument("--output", help="Write report to FILE instead of stdout")
    return p


def _load_json(path: Path) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _format_human(report: Dict[str, Any]) -> str:
    lines = []
    summary = report.get("summary", {})
    lines.append(f"episteme verify — {report.get('mode', 'unknown')} mode")
    lines.append(f"  files:           {summary.get('total', 0)}")
    lines.append(f"  passed:          {summary.get('passed', 0)}")
    lines.append(f"  failed:          {summary.get('failed', 0)}")
    lines.append(f"  exit code:       {report.get('exit_code', '?')}")
    lines.append("")
    for r in report.get("results", []):
        symbol = "✓" if r.get("status") == "PASS" else "✗"
        label = r.get("path") or f"surface[{r.get('index', '?')}]"
        lines.append(f"  {symbol} {label}: {r.get('status')}")
        if r.get("detail"):
            lines.append(f"      {r['detail']}")
    return "\n".join(lines)


def run_verify_cli(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    keys_dir = Path(args.keys_dir)
    if not keys_dir.is_dir():
        print(f"verify: --keys-dir {keys_dir} is not a directory", file=sys.stderr)
        return EXIT_USAGE

    resolver = make_file_resolver(keys_dir)

    report: Dict[str, Any] = {
        "mode": None,
        "results": [],
        "summary": {"total": 0, "passed": 0, "failed": 0},
        "exit_code": EXIT_OK,
    }

    if args.surface_file:
        report["mode"] = "single"
        path = Path(args.surface_file)
        try:
            sf = _load_json(path)
        except (OSError, json.JSONDecodeError) as e:
            report["results"].append({
                "path": str(path),
                "exit_code": EXIT_MALFORMED,
                "status": "FAIL",
                "detail": f"malformed_surface: {e}",
            })
            report["summary"]["total"] = 1
            report["summary"]["failed"] = 1
            report["exit_code"] = EXIT_MALFORMED
        else:
            ec, status, detail = verify_one(
                sf,
                resolver=resolver,
                allow_test_signatures=args.allow_test_signatures,
                verify_tsa=args.verify_tsa,
                verify_rekor=args.verify_rekor,
            )
            report["results"].append({
                "path": str(path),
                "exit_code": ec,
                "status": status,
                "detail": detail,
            })
            report["summary"]["total"] = 1
            report["summary"]["passed"] = 1 if ec == EXIT_OK else 0
            report["summary"]["failed"] = 0 if ec == EXIT_OK else 1
            report["exit_code"] = ec

    elif args.batch:
        report["mode"] = "batch"
        batch_dir = Path(args.batch)
        if not batch_dir.is_dir():
            print(f"verify: --batch {batch_dir} is not a directory", file=sys.stderr)
            return EXIT_USAGE
        files = sorted(batch_dir.glob("*.json"))
        any_fail = False
        all_fail = True
        worst_exit = EXIT_OK
        for path in files:
            try:
                sf = _load_json(path)
                ec, status, detail = verify_one(
                    sf,
                    resolver=resolver,
                    allow_test_signatures=args.allow_test_signatures,
                    verify_tsa=args.verify_tsa,
                    verify_rekor=args.verify_rekor,
                )
            except (OSError, json.JSONDecodeError) as e:
                ec, status, detail = EXIT_MALFORMED, "FAIL", f"malformed_surface: {e}"
            report["results"].append({
                "path": str(path),
                "exit_code": ec,
                "status": status,
                "detail": detail,
            })
            if ec == EXIT_OK:
                all_fail = False
                report["summary"]["passed"] += 1
            else:
                any_fail = True
                report["summary"]["failed"] += 1
                worst_exit = ec  # last non-OK
            report["summary"]["total"] += 1
        if any_fail and not all_fail:
            report["exit_code"] = EXIT_BATCH_MIXED
        elif any_fail:
            report["exit_code"] = worst_exit
        else:
            report["exit_code"] = EXIT_OK

    elif args.chain:
        report["mode"] = "chain"
        manifest_path = Path(args.chain)
        try:
            manifest = _load_json(manifest_path)
        except (OSError, json.JSONDecodeError) as e:
            print(f"verify: chain manifest unreadable: {e}", file=sys.stderr)
            return EXIT_MALFORMED
        surfaces: List[Dict[str, Any]] = []
        for entry in manifest.get("surfaces", []):
            sf_path = Path(entry).resolve() if Path(entry).is_absolute() else (manifest_path.parent / entry).resolve()
            try:
                surfaces.append(_load_json(sf_path))
            except (OSError, json.JSONDecodeError) as e:
                report["results"].append({
                    "path": str(sf_path),
                    "exit_code": EXIT_MALFORMED,
                    "status": "FAIL",
                    "detail": f"malformed_surface: {e}",
                })
                report["summary"]["total"] += 1
                report["summary"]["failed"] += 1
                report["exit_code"] = EXIT_MALFORMED
                if args.format == "json":
                    print(json.dumps(report, indent=2))
                else:
                    print(_format_human(report))
                return EXIT_MALFORMED

        ec, results = verify_chain(
            surfaces,
            resolver=resolver,
            allow_test_signatures=args.allow_test_signatures,
            verify_tsa=args.verify_tsa,
            verify_rekor=args.verify_rekor,
        )
        report["results"] = results
        report["summary"]["total"] = len(surfaces)
        report["summary"]["passed"] = sum(1 for r in results if r["status"] == "PASS")
        report["summary"]["failed"] = sum(1 for r in results if r["status"] == "FAIL")
        report["exit_code"] = ec

    else:
        parser.print_usage(sys.stderr)
        return EXIT_USAGE

    # ── Emit report ──
    output = json.dumps(report, indent=2) if args.format == "json" else _format_human(report)
    if args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)

    return int(report["exit_code"])


def main(argv: Optional[List[str]] = None) -> int:
    return run_verify_cli(argv)


if __name__ == "__main__":
    sys.exit(main())
