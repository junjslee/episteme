# Security Policy

`episteme` is a solo-maintained project. If you've found something
security-relevant, this is how to tell me.

## Reporting a vulnerability

**Don't open a public issue.** Email
[junseong.lee652@gmail.com](mailto:junseong.lee652@gmail.com) with
"episteme security" in the subject line. Include:

- What the vulnerability is.
- A reproduction (steps, commit SHA, or minimal example).
- What impact you think it has.
- Whether you want credit / how to refer to you in any fix note.

You can also open a private report via GitHub's
[Security Advisories](https://github.com/junjslee/episteme/security/advisories/new)
flow if you prefer that channel.

## What I'll do

- Acknowledge receipt within 7 days (faster usually; this is the
  not-on-vacation upper bound).
- Confirm the issue and scope it within 14 days of acknowledgment.
- Coordinate a fix and a disclosure timeline with you.
- Credit you in the release notes if you want (and not if you don't).

## What counts as security-relevant

`episteme` ships a few things that have security-shaped invariants
worth naming explicitly. A report against any of these is in scope:

- **Ed25519 signing path** (`core/practice/`, `src/episteme/surface/`,
  `src/episteme/evidence/`). The signing key is supposed to be
  structurally out of the agent's reach. If the agent can read, copy,
  forge with, or coerce a signature from the operator's key — that's a
  vulnerability.
- **Hash-chain integrity** (Append-Only Hash Chain in `core/`).
  Tamper-evidence is the whole point. If you can mutate a chain entry
  without detection, that's a vulnerability.
- **Reasoning Surface gate** (`core/hooks/reasoning_surface_guard.py`).
  The hook is supposed to refuse high-impact ops without a valid
  Reasoning Surface. Bypasses that aren't already documented in the
  hook's `INDIRECTION_BASH` patterns are in scope.
- **Tier 1 advisory dispatch** (Event 135). The soak gate is supposed
  to keep the advisory path disabled until lived telemetry clears the
  threshold. If you can open the gate without legitimate telemetry —
  that's a vulnerability.
- **PreToolUse hook coverage gaps**. The hook's `HIGH_IMPACT_BASH`
  patterns are supposed to catch the documented irreversible ops. If
  you've found a common irreversible op that bypasses the hook entirely
  via a shape the pattern set doesn't match, please report it.
- **`MANIFEST.sha256` integrity**. Tampering with kernel files without
  detection by `episteme kernel verify` is a vulnerability.

Out of scope (please don't report these as security):

- Coding errors that don't have security consequences.
- DoS-by-design (you can make `pytest` slow if you write a slow test).
- Issues in upstream dependencies — report them to their maintainers.
- Suggestions that the kernel should add a new security feature. Those
  are valid feature requests, just not vulnerability reports.

## Disclosure

I aim for **coordinated disclosure**: I fix the issue, cut a release,
publish a brief note, then credit the reporter. If a vulnerability is
being actively exploited and you have evidence, tell me in the initial
email — that changes the timeline.

If you don't hear back from me within 7 days of an email or private
GitHub report, ping me publicly (without disclosing the vulnerability)
on the issues tab or by another channel you have — I am one person and
emails do occasionally get missed.

## What `episteme` is NOT

For clarity: `episteme` is not a security product. It is a cognitive
governance kernel. It does not protect you from compromised inputs,
hostile networks, or operating-system-level attacks. It is concerned
with the integrity of the operator's *reasoning trail* and signed
decision artifacts — not with general application security. If your
threat model is "the agent's machine is owned," `episteme` cannot help
you.
