"""Reward-agnostic episode statistics for stag_hunt.

Single source of truth for both the grader and the reporter. Everything here
is derived from the game-written ``results.json`` (the ``results`` token of a
Coworld episode bundle), whose schema is declared in
``coworld_manifest.json::game.results_schema``:

    {
      "names":  [str, ...],                 # one per player slot
      "scores": [int, ...],                 # cumulative score per slot
      "stats": {
        "catches":     [[r, b, s, m, e], ...],   # per slot, per prey kind
        "co_captures": [[...N...], ...],          # N×N shared-kill matrix
        "rounds":      [[score per slot], ...]    # per round
      }
    }

Design principle — **reward-agnostic** (do not break on a rebalance):

    Nothing in this module hardcodes prey point values or required coalition
    sizes. Server-side rebalancing of ``StagScoreReward``, ``preyMinPlayers``,
    etc. must not require touching these tools. We read only what the data
    reports: actual ``scores``, actual ``catches`` counts, and the
    ``co_captures`` structure.

    Coalition *depth* falls out of ``co_captures`` structurally. The game
    credits, for a capture with N participants, (N-1) co-capture increments to
    each participant's row — so the matrix sum over a capture is N·(N-1).
    A 4-player kill therefore contributes 12 vs a 2-player kill's 2, and
    "big game is more impressive" emerges from the data rather than from a
    hardcoded ``elephant = 18``.

The only fixed constant is the prey-kind *ordering* of the ``catches`` arrays,
which is part of the results-schema contract (not a balance assumption): the
columns are ``[Rabbit, Boar, Stag, Moose, Elephant]``. If a kind is renamed or
reordered in the schema, update ``PREY_KINDS`` to match.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

# Positional labels for the columns of each ``stats.catches`` row. This mirrors
# the results-schema ordering, NOT any point/difficulty assumption.
PREY_KINDS: tuple[str, ...] = ("Rabbit", "Boar", "Stag", "Moose", "Elephant")


@dataclass(frozen=True)
class PlayerSummary:
    slot: int
    name: str
    score: int
    catches: tuple[int, ...]  # aligned with PREY_KINDS (may be empty/short)

    @property
    def total_catches(self) -> int:
        return sum(self.catches)

    def catches_by_kind(self) -> dict[str, int]:
        return {PREY_KINDS[i]: c for i, c in enumerate(self.catches) if i < len(PREY_KINDS)}


@dataclass(frozen=True)
class CoCapture:
    """An unordered pair of slots that shared at least one kill."""

    a: int
    b: int
    shared: int  # number of captures both slots participated in


@dataclass
class EpisodeStats:
    players: list[PlayerSummary]
    co_captures: list[list[int]]  # N×N, as reported
    rounds: list[list[int]] = field(default_factory=list)

    # ---- basic shape ----

    @property
    def num_players(self) -> int:
        return len(self.players)

    @property
    def scores(self) -> list[int]:
        return [p.score for p in self.players]

    # ---- aggregate catch facts (reward-agnostic) ----

    @property
    def catch_credits_total(self) -> int:
        """Σ over slots & kinds of ``catches`` = Σ over captures of coalition size.

        Each participant of a capture is credited one catch, so a prey caught by
        N players contributes N here.
        """
        return sum(p.total_catches for p in self.players)

    def catches_by_kind(self) -> dict[str, int]:
        totals = {k: 0 for k in PREY_KINDS}
        for p in self.players:
            for i, c in enumerate(p.catches):
                if i < len(PREY_KINDS):
                    totals[PREY_KINDS[i]] += c
        return totals

    # ---- cooperation structure ----

    @property
    def co_pair_credits_total(self) -> int:
        """Sum of all off-diagonal ``co_captures`` entries = Σ over captures of
        N·(N-1) (ordered participant pairs). The diagonal is never written by
        the game, but we exclude it defensively."""
        total = 0
        for i, row in enumerate(self.co_captures):
            for j, v in enumerate(row):
                if i != j:
                    total += v
        return total

    def shared_pairs(self) -> list[CoCapture]:
        """Unordered slot pairs that shared ≥1 kill, with the shared count.

        Uses the symmetric matrix; reads ``co_captures[a][b]`` for a < b.
        """
        out: list[CoCapture] = []
        n = len(self.co_captures)
        for a in range(n):
            for b in range(a + 1, n):
                shared = self.co_captures[a][b] if b < len(self.co_captures[a]) else 0
                if shared > 0:
                    out.append(CoCapture(a=a, b=b, shared=shared))
        out.sort(key=lambda c: c.shared, reverse=True)
        return out

    # ---- round dynamics ----

    def lead_changes(self) -> int:
        """Number of rounds whose leading slot differs from the previous round's.

        Uses per-round scores (actual values). Ties pick the lowest slot; a
        round with no positive score is skipped (no leader)."""
        changes = 0
        prev_leader: int | None = None
        for round_scores in self.rounds:
            if not round_scores or max(round_scores) <= 0:
                continue
            leader = max(range(len(round_scores)), key=lambda i: round_scores[i])
            if prev_leader is not None and leader != prev_leader:
                changes += 1
            prev_leader = leader
        return changes


def from_results(results: dict[str, Any]) -> EpisodeStats:
    """Build :class:`EpisodeStats` from a parsed ``results.json`` object.

    Tolerant of missing/short ``stats`` arrays: a slot with no recorded stats
    gets empty catches and contributes nothing to cooperation metrics.
    """
    names = list(results.get("names") or [])
    scores = list(results.get("scores") or [])
    stats = results.get("stats") or {}
    catches = list(stats.get("catches") or [])
    co_captures = [list(row or []) for row in (stats.get("co_captures") or [])]
    rounds = [list(r or []) for r in (stats.get("rounds") or [])]

    n = max(len(names), len(scores), len(catches))
    players: list[PlayerSummary] = []
    for slot in range(n):
        name = names[slot] if slot < len(names) else f"player_{slot}"
        score = int(scores[slot]) if slot < len(scores) and scores[slot] is not None else 0
        row = tuple(int(x) for x in (catches[slot] if slot < len(catches) else []))
        players.append(PlayerSummary(slot=slot, name=str(name), score=score, catches=row))

    return EpisodeStats(players=players, co_captures=co_captures, rounds=rounds)


# ---------- reward-agnostic scalar helpers (shared by the grader) ----------


def gini(values: list[int | float]) -> float:
    """Gini coefficient of non-negative ``values`` in [0, 1].

    Returns 0.0 for an empty list or all-zero totals (perfect equality / nothing
    to compare). 0 = perfectly equal, →1 = maximally unequal.
    """
    xs = [float(v) for v in values]
    n = len(xs)
    total = sum(xs)
    if n == 0 or total <= 0:
        return 0.0
    abs_diff_sum = sum(abs(xi - xj) for xi in xs for xj in xs)
    return abs_diff_sum / (2.0 * n * total)


def normalized_entropy(counts: dict[str, int] | list[int]) -> float:
    """Shannon entropy of a count distribution, normalized to [0, 1] by the
    log of the number of categories. 0 = all mass in one category, 1 = uniform.

    Normalizing by ``log(len(categories))`` (not log of observed categories)
    means using more of the available prey kinds scores higher.
    """
    values = list(counts.values()) if isinstance(counts, dict) else list(counts)
    total = sum(values)
    k = len(values)
    if total <= 0 or k <= 1:
        return 0.0
    h = 0.0
    for v in values:
        if v > 0:
            p = v / total
            h -= p * math.log(p)
    return h / math.log(k)
