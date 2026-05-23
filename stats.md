# Stag Hunt — eval stats over time

Quick-and-dirty per-change capture-rate snapshots. Each row is one
60s game at default seed unless noted. "self-play" = N copies of the
same bot, no other roster.

## How to reproduce

```sh
# Full game (60s, 32x32, mixed prey):
stag_hunt/eval.sh elephant_hunter,elephant_hunter,elephant_hunter,elephant_hunter \
  --ticks=1440 --no-build

# Focused catch-dynamics loop (elephants only, spawn near players):
stag_hunt/focus_eval.sh 4 300 5 1
```

## Per-commit baseline

| commit | bot | roster | scenario | catches |
|--------|-----|--------|----------|---------|
| 5d99da8 | stag_hunter (orig) | 4 stag_hunter | self-play 60s default | 0 stags |
| 5d99da8 | rabbiteer | 2 rabbiteer + 2 stag_hunter | mixed 60s default | 12 rabbits |
| 2d7b71a | stag_hunter (coop) | 2 stag_hunter | self-play 60s default | 2 stags, 2 boars |
| 2d7b71a | stag_hunter (coop) | 4 stag_hunter | self-play 60s default | 3 stags (uneven) |
| 4d5789a | moose_hunter (rank-side) | 3 moose_hunter | self-play 60s default | 0-1 moose, very flaky |
| 4d5789a | elephant_hunter (rank-side) | 4 elephant_hunter | self-play 60s default | 0-1 elephants |
| 4fac0a7 | modeler | modeler + 3 rabbiteer | mixed 60s default | modeler 13r+2s, top score |
| 5af7b44 | (server: flee + think tuning) | 3 moose_hunter | self-play 60s default | 2-3 moose |
| 5af7b44 | (server: flee + think tuning) | 4 elephant_hunter | self-play 60s default | 0-1 elephants |
| aabc444 | elephant: square-by-square + trample-and-stop | 4 elephant_hunter | self-play 60s default | 0 (bots not yet adapted) |
| (post-corner+pursuit) | elephant_hunter (corner strategy) | 4 elephant_hunter | self-play 60s default | 0-1 (timing rare) |
| (post-min-max-dist picker) | moose_hunter | 3 moose_hunter | self-play 60s default | **4-5 moose consistent** |
| (post-min-max-dist picker) | elephant_hunter | 4 elephant_hunter | self-play 60s default | 0-1 (still flaky) |
| (post-indifferent-cadence) | elephant_hunter | 4 elephant_hunter | self-play 60s default | 0 elephants in 5/5 focus rounds |
| (focus + centroid spawn) | elephant_hunter | 4 elephant_hunter | focus_eval 4 600 5 (stationary) | 4 captures in 2/5 rounds |
| (focus + moving elephant) | elephant_hunter | 4 elephant_hunter | focus_eval 4 600 5 | **6 captures over 5 rounds (1.2/round avg)** |

## Open issues snapshot (as of this writing)

- **Moose hunting is solid.** 3 moose_hunters reliably catch 4-5 moose
  per 60s game across seeds. Per-hunter score ~40-50 pts. ✓
- **Elephant capture is still rare even in focused-spawn mode.** 4
  elephant_hunters with elephants spawning near the player cluster
  still catch 0/5 in `focus_eval.sh 4 300 5 1`. The bots position at
  the four diagonal corners (chebyshev 2 around the elephant), but
  the elephant moves before all four step onto cardinal sides in the
  same tick. The synchronized-dash needs more work, or the elephant
  cadence needs to be slower than the player cadence (currently
  elephant min 12 ticks, max 24; player move cooldown 5 ticks — so a
  hunter has only 2-5 moves to converge before the elephant relocates).
- **Stag captures are noisy.** 0-3 per game depending on seed.
- **User-facing trample feel.** Verified mid-iteration: too aggressive
  was due to scaling cadence with nearby hunters; reverted to flat
  12-24 tick cadence and added "skip wall directions when picking" so
  the elephant doesn't preferentially attack hunters who form a wall.

## Methodology notes

- Seeds tried: 5744151 (default), 1, 42, 99, 7. Most numbers above
  are at default; per-seed variance is logged in commit messages.
- "Capture rate" is wall-clock catches per minute, derived from
  `events.jsonl`. The `catch breakdown` block at the end of each
  eval.sh run shows per-kind counts.
- Bots all start clustered near map center (within ±4 tiles of (16,
  16)). Prey spawn random across the 32x32 map (except in focus mode).
