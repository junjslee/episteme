"""Surface + key filesystem storage.

Default storage layout under `EPISTEME_ROOT` (defaults to `<cwd>/.episteme`):

    .episteme/
    ├── keys/
    │   ├── operator_signing.key          ← private key, mode 0600
    │   ├── operator_signing.pub          ← public key (also fingerprint file)
    │   └── <fingerprint>.pub             ← additional pubkey copies for auditor
    └── surfaces/
        ├── active.txt                    ← single line: <surface_id>
        ├── 2026-05-12/
        │   └── <surface_id>.json         ← signed surface artifact
        └── <surface_id>.json             ← legacy flat layout fallback

The date-bucketed layout keeps large surface stores manageable; the flat
layout is preserved so older fixtures continue to round-trip cleanly.
"""
from __future__ import annotations

# pyright: reportMissingImports=false
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional


def episteme_root(cwd: Optional[Path] = None) -> Path:
    """Resolve EPISTEME_ROOT.

    Precedence: explicit override env → cwd / .episteme.
    """
    override = os.environ.get("EPISTEME_ROOT")
    if override:
        return Path(override)
    return (cwd or Path.cwd()) / ".episteme"


def keys_dir(root: Optional[Path] = None) -> Path:
    return (root or episteme_root()) / "keys"


def surfaces_dir(root: Optional[Path] = None) -> Path:
    return (root or episteme_root()) / "surfaces"


def active_surface_pointer(root: Optional[Path] = None) -> Path:
    return surfaces_dir(root) / "active.txt"


def ensure_storage(root: Optional[Path] = None) -> None:
    """Idempotent creation of the storage tree with correct permissions."""
    r = root or episteme_root()
    (r / "keys").mkdir(parents=True, exist_ok=True)
    (r / "surfaces").mkdir(parents=True, exist_ok=True)
    # Tighten keys/ to operator-only (best effort; Windows ACLs are different).
    try:
        os.chmod(r / "keys", stat.S_IRWXU)
    except (PermissionError, NotImplementedError):
        pass


# ─── Surface persistence ─────────────────────────────────────────────────


def _today_bucket() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def surface_path_for(surface_id: str, *, root: Optional[Path] = None) -> Path:
    """Path where a newly-signed surface for `surface_id` will be written."""
    return surfaces_dir(root) / _today_bucket() / f"{surface_id}.json"


def write_surface(surface_id: str, signed_dict: dict, *, root: Optional[Path] = None) -> Path:
    """Persist a signed surface dict to disk under the date-bucketed layout."""
    path = surface_path_for(surface_id, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(signed_dict, indent=2, sort_keys=True), encoding="utf-8")
    return path


def find_surface(surface_id: str, *, root: Optional[Path] = None) -> Optional[Path]:
    """Locate a signed surface by id, searching date buckets + flat fallback."""
    sd = surfaces_dir(root)
    # Date-bucketed layout
    for date_dir in sorted(sd.glob("*"), reverse=True):
        if not date_dir.is_dir():
            continue
        candidate = date_dir / f"{surface_id}.json"
        if candidate.exists():
            return candidate
    # Flat fallback
    flat = sd / f"{surface_id}.json"
    if flat.exists():
        return flat
    return None


def iter_surfaces(*, root: Optional[Path] = None) -> Iterator[Path]:
    """Yield every surface JSON file under the surfaces dir, newest first."""
    sd = surfaces_dir(root)
    if not sd.exists():
        return
    candidates = []
    for path in sd.rglob("*.json"):
        # Skip the active.txt and non-surface files
        if path.name == "active.txt":
            continue
        try:
            candidates.append((path.stat().st_mtime, path))
        except OSError:
            continue
    for _, path in sorted(candidates, reverse=True):
        yield path


def set_active_surface(surface_id: str, *, root: Optional[Path] = None) -> Path:
    """Update the active-surface pointer."""
    ptr = active_surface_pointer(root)
    ptr.parent.mkdir(parents=True, exist_ok=True)
    ptr.write_text(surface_id, encoding="utf-8")
    return ptr


def get_active_surface_id(*, root: Optional[Path] = None) -> Optional[str]:
    ptr = active_surface_pointer(root)
    if not ptr.exists():
        return None
    return ptr.read_text(encoding="utf-8").strip() or None


def get_active_surface_path(*, root: Optional[Path] = None) -> Optional[Path]:
    sid = get_active_surface_id(root=root)
    if not sid:
        return None
    return find_surface(sid, root=root)


# ─── Key persistence ─────────────────────────────────────────────────────


def write_keypair(privkey_hex: str, pubkey_hex: str, *, root: Optional[Path] = None) -> tuple[Path, Path]:
    """Write a fresh keypair to .episteme/keys/.

    Files written:
      keys/operator_signing.key  ← private key hex, mode 0600
      keys/operator_signing.pub  ← public key hex
      keys/<fingerprint>.pub     ← duplicate, named by fingerprint
    """
    from core.ptsp.canonical import sha256_hex

    ensure_storage(root)
    kdir = keys_dir(root)
    priv_path = kdir / "operator_signing.key"
    pub_path = kdir / "operator_signing.pub"
    priv_path.write_text(privkey_hex, encoding="utf-8")
    pub_path.write_text(pubkey_hex, encoding="utf-8")
    try:
        os.chmod(priv_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    except (PermissionError, NotImplementedError):
        pass
    fp = sha256_hex(bytes.fromhex(pubkey_hex))
    fp_path = kdir / f"{fp}.pub"
    fp_path.write_text(pubkey_hex, encoding="utf-8")
    return priv_path, pub_path


def read_keypair(*, root: Optional[Path] = None) -> Optional[tuple[str, str]]:
    """Read the active keypair, or return None if not present."""
    kdir = keys_dir(root)
    priv = kdir / "operator_signing.key"
    pub = kdir / "operator_signing.pub"
    if not priv.exists() or not pub.exists():
        return None
    return (priv.read_text(encoding="utf-8").strip(), pub.read_text(encoding="utf-8").strip())


def read_public_key_by_fingerprint(fingerprint: str, *, root: Optional[Path] = None) -> Optional[str]:
    """Resolve a pubkey by fingerprint from .episteme/keys/."""
    kdir = keys_dir(root)
    fp_path = kdir / f"{fingerprint}.pub"
    if fp_path.exists():
        return fp_path.read_text(encoding="utf-8").strip()
    return None
