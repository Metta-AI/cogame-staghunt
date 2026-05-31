# Coworld compliance + grader & reporter — design

Date: 2026-05-30

## Goals

1. Make `coworld_manifest.json` compliant with the current Coworld manifest
   schema (`Metta-AI/metta` → `packages/coworld/src/coworld/coworld_manifest_schema.json`).
2. Ship a game-specific **grader** (scalar "how interesting was this episode,
   w.r.t. multi-agent collaboration") and **reporter** (sports-commentator /
   newspaper write-up of an episode).

## Part 1 — Manifest compliance

The manifest was authored against an older schema. Five violations:

1. **Missing `reporter[]`** — now a required top-level array (`minItems: 1`).
2. **Missing `game.docs`** — required; needs exactly one `rules.md` page and one
   `play_*.md` page.
3. **`game.protocols.player`/`.global` are bare strings** — must be doc objects
   `{ "type": "uri", "value": "https://…" }`.
4. **`player[]` entries nest a `runnable` wrapper** — schema wants *flat* role
   specs: `type`, `image`, `id`, `name`, `description` (+ optional
   `run`/`env`/`source_url`). `runnable` is not an allowed key.
5. **`certification`** uses `variant_id` + `initial_params` — must be
   `{ "game_config": {…}, "players": [ { "player_id": … } ] }`.

Also add a `grader[]` entry (optional today, "future required").

## Part 2 — Grader & reporter

### Image strategy

A single Python image `ghcr.io/malcolmocean/bitworld-stag-hunt-tools:latest`,
separate from the Nim game image. Two entrypoints (`run` overrides) select
grader vs reporter. Contents:

- `tools/staghunt_tools/_sdk/` — vendored Coworld reporter SDK (bundle reader,
  URI I/O, deterministic report-zip builder). Source: `Metta-AI/reporters`,
  mirrored via the paintarena example.
- `tools/staghunt_tools/episode.py` — shared, **reward-agnostic** stats derived
  from `results.json`. Single source of truth for grader + reporter.
- `tools/staghunt_tools/grader.py` — reads `COGAME_EPISODE_BUNDLE_URI`, writes a
  grade JSON to `COGAME_GRADE_URI`.
- `tools/staghunt_tools/reporter.py` — reads the bundle, writes a report zip to
  `COGAME_REPORT_URI`.

### Reward-agnostic principle (load-bearing)

The grader and the reporter's computed facts **never hardcode prey point values
or coalition sizes**. Rewards/coalition rules can be rebalanced server-side
without touching these tools. They read only:

- `scores` — actual per-player cumulative scores (whatever the current reward
  table produces).
- `stats.catches` — per-player `[Rabbit, Boar, Stag, Moose, Elephant]` counts
  (positional order is fixed by the results schema; values are data).
- `stats.co_captures` — N×N shared-kill matrix. For a capture with N
  participants, each participant's row gains (N−1). Solo kills add nothing.
- `stats.rounds` — per-round score arrays (for lead changes).

Coalition *depth* therefore falls out of the co-capture mass structurally: a
4-player kill yields 12 ordered-pair credits vs a 2-player kill's 2, so "big
game is more impressive" emerges from the data, not a hardcoded `elephant=18`.

### Grader score (∈ [0,1])

Weighted composite, each component echoed in the output for provenance:

| Component | Weight | Definition (reward-agnostic) |
| --- | --- | --- |
| Cooperation depth | 0.45 | `Σ co_pair_credits / Σ catch_credits`, normalized by `(P−1)`. Rewards larger coordinated captures. |
| Cooperation breadth | 0.25 | fraction of player-pairs with ≥1 shared kill. |
| Competitive balance | 0.20 | `1 − Gini(scores)` using actual final scores. |
| Prey diversity | 0.10 | normalized Shannon entropy over aggregated catches-by-kind. |

Output: `{ "grader_id", "score", "components": {…}, "weights": {…} }`.

### Reporter

1. Compute the shared facts (actual scores, per-player prey breakdown, who
   teamed with whom, most-coordinated pairings, round-by-round lead changes).
2. Ask Claude **via AWS Bedrock** (`AnthropicBedrock`; model from
   `STAGHUNT_REPORTER_MODEL`, default a Claude Opus inference profile; region
   from `AWS_REGION`) for a sports-commentator/newspaper write-up **grounded
   strictly in the supplied facts** (no invented events; use the real numbers).
3. **Graceful fallback**: on any Bedrock unavailability/error, emit a
   deterministic templated narrative from the same facts, so the reporter never
   fails. stderr logs which path was taken.

Output zip: `manifest.json` (`render: "report.md"`) + `report.md` +
`stats.json`.

### Execution model

Both roles are **on-demand** per the Coworld spec (triggered by a CLI/platform
action, not the episode runner). So the reporter's Opus call happens only when a
human wants a write-up — cost is a non-issue at that cadence.

## Testing

- Unit tests for `episode.py` and the grader scoring (pure functions): boring
  all-rabbit episode → low score; coordinated big-game episode → high score;
  reward-rebalance invariance (scaling/relabeling points doesn't move the
  coordination components).
- Full local run: `eval.sh` produces a real `results.json`; assemble a bundle
  zip; run grader + reporter against it (`file://`); inspect outputs. Build the
  Docker image.
