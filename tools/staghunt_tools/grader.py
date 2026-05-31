"""stag_hunt grader — scalar "how interesting was this episode" score.

Implements the Coworld grader contract (``docs/roles/GRADER.md`` in
``Metta-AI/metta``): a short-lived process that reads an episode bundle from
``COGAME_EPISODE_BUNDLE_URI`` and writes a grade JSON to ``COGAME_GRADE_URI``.

The score (∈ [0, 1]) rewards *interesting multi-agent collaboration*. It is
**reward-agnostic** — see ``episode.py`` — so rebalancing prey points or
coalition sizes server-side never invalidates the grader.

Score = weighted sum of four components, each in [0, 1]:

| Component            | Weight | Meaning                                              |
| -------------------- | ------ | ---------------------------------------------------- |
| cooperation_depth    | 0.45   | how coordinated captures were (co-capture mass).     |
| cooperation_breadth  | 0.25   | fraction of player-pairs that ever shared a kill.    |
| competitive_balance  | 0.20   | 1 − Gini(actual scores); close games are livelier.   |
| prey_diversity       | 0.10   | variety of prey kinds hunted (normalized entropy).   |

A boring all-solo-rabbit episode lands near 0; a tightly-coordinated big-game
episode with several teaming players lands near 1.
"""

from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import dataclass

from ._sdk import BundleReader, write_uri
from .episode import EpisodeStats, from_results, gini, normalized_entropy

GRADER_ID = "stag-hunt-collab-grader"

WEIGHTS: dict[str, float] = {
    "cooperation_depth": 0.45,
    "cooperation_breadth": 0.25,
    "competitive_balance": 0.20,
    "prey_diversity": 0.10,
}


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def cooperation_depth(stats: EpisodeStats) -> float:
    """Σ co-pair-credits / Σ catch-credits, normalized by (P−1) into [0, 1].

    co-pair-credits sum to Σ N·(N-1) over captures; catch-credits to Σ N. Their
    ratio is the mean (coalition_size − 1) weighted by coalition size, which is
    maximized at (P−1) when every capture uses all P players.
    """
    p = stats.num_players
    if p < 2:
        return 0.0
    credits = stats.catch_credits_total
    if credits <= 0:
        return 0.0
    raw = stats.co_pair_credits_total / credits  # ∈ [0, p-1]
    return _clamp01(raw / (p - 1))


def cooperation_breadth(stats: EpisodeStats) -> float:
    p = stats.num_players
    if p < 2:
        return 0.0
    possible = p * (p - 1) // 2
    return _clamp01(len(stats.shared_pairs()) / possible)


def competitive_balance(stats: EpisodeStats) -> float:
    # Only meaningful once someone has scored; an all-zero episode had no
    # competition to speak of, so it contributes nothing rather than a
    # spurious "perfectly balanced" 1.0.
    if sum(stats.scores) <= 0:
        return 0.0
    return _clamp01(1.0 - gini(stats.scores))


def prey_diversity(stats: EpisodeStats) -> float:
    return _clamp01(normalized_entropy(stats.catches_by_kind()))


@dataclass(frozen=True)
class Grade:
    grader_id: str
    score: float
    components: dict[str, float]
    weights: dict[str, float]
    meta: dict[str, int]

    def to_json(self) -> bytes:
        payload = {
            "grader_id": self.grader_id,
            "score": round(self.score, 4),
            "components": {k: round(v, 4) for k, v in self.components.items()},
            "weights": self.weights,
            "meta": self.meta,
        }
        return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def grade_episode(stats: EpisodeStats) -> Grade:
    components = {
        "cooperation_depth": cooperation_depth(stats),
        "cooperation_breadth": cooperation_breadth(stats),
        "competitive_balance": competitive_balance(stats),
        "prey_diversity": prey_diversity(stats),
    }
    score = sum(WEIGHTS[k] * v for k, v in components.items())
    if not math.isfinite(score):
        score = 0.0
    return Grade(
        grader_id=GRADER_ID,
        score=_clamp01(score),
        components=components,
        weights=WEIGHTS,
        meta={
            "num_players": stats.num_players,
            "catch_credits_total": stats.catch_credits_total,
            "co_pair_credits_total": stats.co_pair_credits_total,
            "shared_pairs": len(stats.shared_pairs()),
            "lead_changes": stats.lead_changes(),
        },
    )


def run(bundle_uri: str, grade_uri: str) -> Grade:
    with BundleReader(bundle_uri) as bundle:
        inner = bundle.inner_manifest()
        if inner.status != "success":
            raise RuntimeError(f"bundle status={inner.status!r}; cannot grade a failed episode")
        results = bundle.read_json("results")
    stats = from_results(results)
    grade = grade_episode(stats)
    write_uri(grade_uri, grade.to_json(), content_type="application/json")
    print(f"[{GRADER_ID}] score={grade.score:.4f} → {grade_uri}", file=sys.stderr, flush=True)
    return grade


def main() -> None:
    run(
        bundle_uri=os.environ["COGAME_EPISODE_BUNDLE_URI"],
        grade_uri=os.environ["COGAME_GRADE_URI"],
    )


if __name__ == "__main__":
    main()
