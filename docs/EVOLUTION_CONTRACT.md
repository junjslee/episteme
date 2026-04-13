     1|# Evolution Contract v1
     2|
     3|Purpose: define a safe, auditable self-evolution loop for the cognitive-os cognitive+execution harness.
     4|
     5|## Product identity
     6|
     7|Public product identity: `cognitive-os`.
     8|CLI/package/repo identity: `cognitive-os`.
     9|
    10|Positioning:
    11|- cognitive-os is the cognitive + execution harness model.
    12|- `cognitive-os` is the distribution and CLI surface.
    13|
    14|## Core loop
    15|
    16|Every evolution cycle follows this immutable sequence:
    17|1. Propose (Generator role)
    18|2. Critique (Critic role)
    19|3. Replay + evaluate (deterministic task suite)
    20|4. Gate decision (promote/reject)
    21|5. Promote with rollback reference (human-approved by default)
    22|
    23|## Evolution episode
    24|
    25|Each run produces an `EvolutionEpisode` record with:
    26|- `episode_id`
    27|- `parent_episode_id` (optional)
    28|- `hypothesis`
    29|- `mutation`
    30|- `suite_ref`
    31|- `metrics_before`
    32|- `metrics_after`
    33|- `gate_result`
    34|- `decision` (`promoted | rejected | rolled_back`)
    35|- `rollback_ref`
    36|- `provenance`
    37|
    38|## Role split
    39|
    40|### Generator
    41|- Proposes bounded changes only.
    42|- Must declare expected improvement and risk.
    43|
    44|### Critic
    45|- Attempts to falsify the proposal.
    46|- Flags safety, regression, and overfitting risks.
    47|- Must provide at least one disconfirmation test.
    48|
    49|## Mutation library (bounded)
    50|
    51|Allowed mutation types in v1:
    52|- `prompt_policy_tweak`
    53|- `retrieval_policy_tweak`
    54|- `planning_depth_tweak`
    55|- `tool_selection_rule_tweak`
    56|- `handoff_format_tweak`
    57|
    58|Disallowed in v1:
    59|- direct secret or auth policy modifications
    60|- unattended destructive command policy loosening
    61|- changes outside declared mutation target scope
    62|
    63|## Replay and evaluation
    64|
    65|Candidate changes must run against:
    66|1) baseline replay set
    67|2) hard-failure replay buffer
    68|3) optional fresh tasks
    69|
    70|Required metrics:
    71|- `task_success_rate`
    72|- `safety_violation_count`
    73|- `latency_ms_p50`
    74|- `token_cost`
    75|- `style_fit_score` (alignment to operator/cognitive policy)
    76|
    77|## Promotion gates
    78|
    79|Promotion requires all gates to pass:
    80|- success delta >= configured threshold
    81|- no safety regression
    82|- latency/cost within budget envelope
    83|- deterministic stability across repeated seeded runs
    84|- critic sign-off present
    85|
    86|Default policy: human approval required before promotion.
    87|
    88|## Distillation lanes
    89|
    90|Memory promotion pipeline:
    91|- lane A: raw traces (high-volume, short TTL)
    92|- lane B: episodic summaries (candidate lessons)
    93|- lane C: canonical policy memory (only repeated winners)
    94|
    95|Promotion rule:
    96|- lane B -> C requires repeated validated wins and no safety regression.
    97|
    98|## Conflict and rollback
    99|
   100|- No silent replacement of canonical policy.
   101|- Every promotion must include rollback reference.
   102|- Rollback updates episode state to `rolled_back` and links reason/evidence.
   103|
   104|## Schemas
   105|
   106|- `core/schemas/evolution/evolution_episode.json`
   107|- `core/schemas/evolution/mutation.json`
   108|- `core/schemas/evolution/evaluation_report.json`
   109|- `core/schemas/evolution/gate_policy.json`
   110|
   111|## Starter CLI model
   112|
   113|Current command surface (implemented):
   114|- `cognitive-os evolve run`
   115|- `cognitive-os evolve report <episode_id>`
   116|- `cognitive-os evolve promote <episode_id>`
   117|- `cognitive-os evolve rollback <episode_id>`
   118|
   119|Canonical command:
   120|- `cognitive-os evolve ...`
   121|