# Stag Hunt tools — grader & reporter

Two Coworld *supporting runnables* that consume a finished episode and emit
post-episode artifacts. Both are **on-demand** (triggered by a CLI/platform
action, not the episode runner) and read the episode bundle from
`COGAME_EPISODE_BUNDLE_URI`.

- **`stag_hunt.grader`** → writes a scalar grade JSON to `COGAME_GRADE_URI`.
  "How interesting was this episode w.r.t. multi-agent collaboration?", 0–1.
- **`stag_hunt.reporter`** → writes a report zip to `COGAME_REPORT_URI`:
  a sports-commentator / newspaper recap (`report.md`) plus `stats.json`.

Both are wired into `coworld_manifest.json` (`grader[]` / `reporter[]`) and ship
in `ghcr.io/malcolmocean/bitworld-stag-hunt-tools:latest`.

## Reward-agnostic by design

Neither tool hardcodes prey point values or required coalition sizes, so
server-side rebalancing (changing `StagScoreReward`, `preyMinPlayers`, …) never
invalidates them. They read only what `results.json` reports:

- `scores` — actual per-player totals (whatever the current reward table yields).
- `stats.catches` — per-player `[Rabbit, Boar, Stag, Moose, Elephant]` counts.
- `stats.co_captures` — N×N shared-kill matrix.
- `stats.rounds` — per-round scores.

Coalition *depth* falls out of `co_captures` structurally: a capture by N
hunters credits each participant's row `(N−1)`, so a 4-hunter elephant kill
contributes 12 vs a 2-hunter kill's 2. "Big game is more impressive" is learned
from the data, not from a baked-in `elephant = 18`. See `staghunt_tools/episode.py`.

## Grader score

Weighted composite in `[0, 1]` (`staghunt_tools/grader.py`); each component is
echoed in the output for provenance:

| Component | Weight | Definition (reward-agnostic) |
| --- | --- | --- |
| `cooperation_depth` | 0.45 | `Σ co_pair_credits / Σ catch_credits`, normalized by `(P−1)`. |
| `cooperation_breadth` | 0.25 | fraction of player-pairs with ≥1 shared kill. |
| `competitive_balance` | 0.20 | `1 − Gini(scores)` from actual scores. |
| `prey_diversity` | 0.10 | normalized Shannon entropy over catches-by-kind. |

## Reporter

Computes the same reward-agnostic facts, then narrates them with **Claude via
AWS Bedrock**, grounded strictly in the data. On any Bedrock
unavailability/error it falls back to a deterministic templated recap, so it
never fails.

Env:

| Var | Default | Purpose |
| --- | --- | --- |
| `STAGHUNT_REPORTER_MODEL` | `us.anthropic.claude-opus-4-7` | Bedrock model / inference-profile id. |
| `AWS_REGION` | (AWS SDK default) | Bedrock region. |
| `STAGHUNT_REPORTER_NO_LLM` | unset | If set, always use the deterministic narrative. |

AWS credentials are resolved by the standard AWS SDK chain (env vars, profile,
or instance role).

## Develop & test

```bash
cd tools
python3 -m venv .venv && . .venv/bin/activate
pip install pydantic requests pytest        # + anthropic[bedrock] for live narration
python -m pytest tests/ -q
```

## Run end-to-end locally

`run_local.py` wraps a game-written `scores.json` in a minimal episode bundle
and runs both tools over `file://` URIs — the same contract the platform uses:

```bash
./eval.sh big_game_hunter,big_game_hunter,big_game_hunter,big_game_hunter \
  --no-build --ticks=1500 --rounds=2 --out=tmp/ep
python tools/run_local.py tmp/ep/scores.json tmp/ep/out
# add STAGHUNT_REPORTER_NO_LLM=1 to force the deterministic narrative
```
