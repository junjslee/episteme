# How to author a Signed Reasoning Surface

**Audience:** developer-operator preparing to authorize an irreversible AI-assisted decision.
**Goal:** end up with a cryptographically signed `signed-surface@1.0` artifact under `.episteme/surfaces/` that the validator hook will accept and an auditor's standalone verifier will pass.

---

## 1. One-time setup

```bash
# (optional) install production-grade Ed25519 signing
pip install 'episteme[signing]'        # installs PyNaCl
# without this, episteme uses a structurally-distinguishable HMAC-SHA256
# fallback that the verifier rejects by default (see §6).
```

The first time you run `episteme surface author`, a keypair is generated and persisted to:

```
.episteme/keys/operator_signing.key   # private key, mode 0600
.episteme/keys/operator_signing.pub   # public key
.episteme/keys/<fingerprint>.pub      # duplicate, named by fingerprint
```

If you want to use an existing key, drop the hex bytes into `operator_signing.key` and `operator_signing.pub` before the first author call.

---

## 2. Author a surface — interactive (recommended first time)

```bash
episteme surface author --interactive
```

You will be prompted for:

| Field | Min | Notes |
|---|---|---|
| `core_question` | 20 chars | One sentence: what is this decision answering? |
| `reversibility` | enum | `reversible` or `irreversible` |
| `blast_radius` | enum | `local` / `repo` / `external_service` / `user_visible` / `regulated_artifact` |
| `ai_act_tier` | enum | `minimal` / `limited` / `high` / `unacceptable` |
| One unknown | `cost_of_ignorance` ≥ 30 chars | What does it cost if you proceed without knowing? |
| One assumption | with `if_wrong_then` + `detectability` enum | Pre-execution / post-execution-soft / post-execution-irreversible |
| One disconfirmation condition | observable + measurement method | What would invalidate this plan if you saw it? |
| `decision.choice` | enum | `proceed` / `stop` / `audit` |
| `decision.confidence` | float | 0.0 to 1.0, your subjective probability the choice is correct |
| `stop_rollback_path` | ≥ 10 chars | Concrete steps to undo if you proceed and it goes wrong |
| `blueprint_invoked` | enum | `consequence_chain` is the default |

After collection, the body is validated, signed, and persisted. The CLI prints the new `surface_id` and marks it as the active surface (`.episteme/surfaces/active.txt`).

---

## 3. Author a surface — non-interactive (CI / scripting)

```bash
episteme surface author \
  --core-question "Should I run the migration on prod-us-east now?" \
  --reversibility irreversible \
  --blast-radius regulated_artifact \
  --ai-act-tier high \
  --decision-choice proceed \
  --decision-confidence 0.78 \
  --stop-rollback-path "psql -c 'SELECT pg_cancel_backend(pid)' against the migration session" \
  --blueprint consequence_chain \
  --with-tsa --with-rekor
```

For richer bodies (multiple unknowns, knowns with source artifacts, etc.), prepare a JSON file matching the schema and pass `--body-file path/to/body.json`.

---

## 4. Verify the active surface (self-test)

```bash
episteme surface verify --allow-test-signatures
```

This runs the same logic the standalone `episteme verify` CLI uses. Exit code 0 means the surface signs and verifies cleanly. Pass `--verify-tsa --verify-rekor` to also exercise the TSA + transparency-log shapes.

If you have PyNaCl installed and signed with production Ed25519, drop `--allow-test-signatures`. The verifier rejects test-mode signatures by default (see §6).

---

## 5. Use the surface for an irreversible action (Claude Code)

If you have wired the additive PreToolUse validator hook into `.claude/settings.json` (see `skills/compliance-evidence-layer/` for the snippet) and exported:

```bash
export EPISTEME_SIGNED_SURFACE_REQUIRED=1
export EPISTEME_ALLOW_TEST_SIGNATURES=1   # only if not using PyNaCl
```

… then Claude Code will block any irreversible-class tool call (`git push`, `rm -rf`, `kubectl apply`, etc.) until a valid, signed, fresh (< 15 min old) Reasoning Surface exists that declares `reversibility = "irreversible"`.

The block fires before the tool runs. Re-author the surface to retry.

---

## 6. Why test mode is structurally distinguishable from production

The `core.signing.ed25519_compat` module exposes two modes:

| Mode | Signature prefix | Mechanism | When |
|---|---|---|---|
| Production | `ed25519:<128-hex>` | PyNaCl Ed25519 over JCS-canonical payload | PyNaCl installed |
| Test fallback | `test-hmac:<64-hex>` | HMAC-SHA256 (NOT secure) | PyNaCl absent |

The verifier looks at the prefix on every signature. Test mode is **rejected by default** — `episteme verify` requires `--allow-test-signatures` and the validator hook requires `EPISTEME_ALLOW_TEST_SIGNATURES=1`. Real audit-grade signing must run on a host with PyNaCl. The dual-mode design preserves the kernel's `dependencies = []` posture (zero hard deps) while making it impossible to silently ship test signatures into a production audit.

---

## 7. What the signed artifact looks like

```
.episteme/surfaces/2026-05-12/surf-20260512T061805-229241e6.json
```

The full schema is documented at `core/signing/canonical_surface.py` and mirrored in `~/.hermes/schemas/signed-surface-v1.0.md` after `episteme sync`. Top-level structure: `envelope`, `surface`, `attestation`, `self_hash`. See `docs/COMPLIANCE_CROSSWALK.md` for the field-to-clause mapping against EU AI Act / NIST / financial-services frameworks.
