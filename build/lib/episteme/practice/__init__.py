"""`episteme practice` CLI — make the practice tangible.

Three subcommands:

  episteme practice walk        Narrated walkthrough of the 5-stage practice
                                with worked example. No surface persisted.
                                For onboarding + 60-second comprehension.

  episteme practice retro       Retrospective over signed surfaces in a time
                                window. Surfaces gap observations (which
                                cognitive moves were repeatedly shallow or
                                skipped). Not a single-score grade.

  episteme practice demo        Output a worked-example signed surface to
                                stdout, narrated stage-by-stage. For grokking
                                what a well-practiced surface looks like.

The practice CLI is OUTPUT-ONLY. It does not author or modify any signed
surface. `episteme surface author --interactive` remains the canonical
authoring path.
"""
from __future__ import annotations

# pyright: reportMissingImports=false
from episteme.practice._cli import build_parser, run_practice_cli, main

__all__ = ["build_parser", "run_practice_cli", "main"]
