"""release-please-config.json must pin the prerelease versioning strategy.

Failure mode this guards (Event 146, audit-confirmed): the config declared
`prerelease: true` + `prerelease-type: rc` but NO `versioning` key. Release-
please then falls back to the `default` versioning strategy, which strips the
`-rc` suffix, bumps the BASE version per conventional commits, and re-appends
`-rc1` every time. Result: 11/11 pipeline releases were `-rc1`
(1.1.0-rc1 .. 1.9.0-rc1), rc2 was unreachable, and a `feat:` advanced the
minor instead of iterating the rc counter.

The fix is a single key: `"versioning": "prerelease"` at the package level.
Under that strategy release-please increments the prerelease counter and holds
the base (1.9.0-rc1 + new fix:/feat: -> 1.9.0-rc2). This test asserts the key
is present and set to the strategy that produces that behaviour, so an
accidental removal (which silently restores the rc-treadmill) fails CI instead
of shipping.

Doc-verified against googleapis/release-please (action pinned to @v4):
- src/versioning-strategies/prerelease.ts (bumpPrerelease increment + the
  `if (!this.prerelease)` graduation branch)
- docs/customizing.md (the `versioning` key and its strategy values)
- schemas/config.json (`versioning` is a valid per-package property)
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "release-please-config.json"

# The strategy that makes the rc counter iterate instead of resetting.
# `prerelease-type: rc` is only honoured as a counter-increment under this
# strategy; under the `default` strategy it is re-appended fresh every bump.
PRERELEASE_STRATEGY = "prerelease"

# The full set of versioning strategies release-please accepts. Kept here so a
# typo (e.g. "prerlease") is caught as an invalid-value failure, not silently
# treated as an unknown-but-tolerated string by the loose JSON schema (the
# schema types `versioning` as a bare string with no enum).
VALID_STRATEGIES = frozenset(
    {
        "default",
        "always-bump-patch",
        "always-bump-minor",
        "always-bump-major",
        "service-pack",
        "prerelease",
    }
)


class ReleasePleaseConfig(unittest.TestCase):
    """The versioning strategy is load-bearing config, not decoration."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.pkg = cls.config["packages"]["."]

    def test_versioning_key_present(self) -> None:
        self.assertIn(
            "versioning",
            self.pkg,
            "release-please-config.json packages['.'] must set a 'versioning' "
            "strategy; absent means the default strategy re-appends -rc1 every "
            "bump (Event 146 rc-treadmill).",
        )

    def test_versioning_is_prerelease_strategy(self) -> None:
        self.assertEqual(
            self.pkg.get("versioning"),
            PRERELEASE_STRATEGY,
            "versioning must be 'prerelease' so the rc counter iterates "
            "(1.9.0-rc1 -> 1.9.0-rc2, base held) instead of resetting to -rc1.",
        )

    def test_versioning_value_is_a_valid_strategy(self) -> None:
        self.assertIn(
            self.pkg.get("versioning"),
            VALID_STRATEGIES,
            "versioning must be one of the release-please strategy names; the "
            "JSON schema types it as a bare string and will not catch a typo.",
        )

    def test_prerelease_flags_consistent_with_strategy(self) -> None:
        # The prerelease strategy only produces rc iteration when the prerelease
        # flag/type are also set; guard the trio so a partial edit that breaks
        # the contract (e.g. dropping prerelease-type) fails here.
        self.assertTrue(
            self.pkg.get("prerelease"),
            "prerelease:true is required for the prerelease strategy to emit "
            "an -rc suffix.",
        )
        self.assertEqual(
            self.pkg.get("prerelease-type"),
            "rc",
            "prerelease-type:'rc' is the suffix the counter iterates.",
        )


if __name__ == "__main__":
    unittest.main()
