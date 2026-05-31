"""Tests for the reward-agnostic episode stats."""

from staghunt_tools.episode import PREY_KINDS, from_results, gini, normalized_entropy


def build_results(num_players, captures, scores=None, rounds=None):
    """Build a results.json-shaped dict from a list of captures.

    Each capture is ``(kind_index, [slot, ...])``. Mirrors the game's crediting:
    every participant gets a catch for the kind; every ordered pair of distinct
    participants gets a co-capture increment.
    """
    catches = [[0] * len(PREY_KINDS) for _ in range(num_players)]
    co = [[0] * num_players for _ in range(num_players)]
    for kind, coalition in captures:
        for s in coalition:
            catches[s][kind] += 1
            for o in coalition:
                if o != s:
                    co[s][o] += 1
    return {
        "names": [f"p{i}" for i in range(num_players)],
        "scores": scores if scores is not None else [0] * num_players,
        "stats": {"catches": catches, "co_captures": co, "rounds": rounds or []},
    }


def test_gini_equal_is_zero():
    assert gini([10, 10, 10]) == 0.0


def test_gini_scale_invariant():
    assert abs(gini([1, 2, 3]) - gini([10, 20, 30])) < 1e-12


def test_gini_empty_and_zero():
    assert gini([]) == 0.0
    assert gini([0, 0, 0]) == 0.0


def test_normalized_entropy_single_category_is_zero():
    assert normalized_entropy({"Rabbit": 5, "Boar": 0, "Stag": 0, "Moose": 0, "Elephant": 0}) == 0.0


def test_normalized_entropy_uniform_is_one():
    h = normalized_entropy({k: 3 for k in PREY_KINDS})
    assert abs(h - 1.0) < 1e-12


def test_from_results_tolerates_missing_stats():
    stats = from_results({"names": ["a", "b"], "scores": [3, 1]})
    assert stats.num_players == 2
    assert stats.catch_credits_total == 0
    assert stats.co_pair_credits_total == 0
    assert stats.shared_pairs() == []


def test_co_pair_credits_match_coalition_structure():
    # One 4-player capture → 4*3 = 12 ordered-pair credits; 6 unordered shared pairs.
    stats = from_results(build_results(4, [(4, [0, 1, 2, 3])]))
    assert stats.co_pair_credits_total == 12
    assert len(stats.shared_pairs()) == 6
    assert stats.catch_credits_total == 4


def test_solo_captures_have_no_cooperation():
    stats = from_results(build_results(4, [(0, [0]), (0, [1]), (0, [2]), (0, [3])]))
    assert stats.co_pair_credits_total == 0
    assert stats.shared_pairs() == []
    assert stats.catch_credits_total == 4


def test_lead_changes_counts_swaps():
    stats = from_results(build_results(2, [], rounds=[[5, 1], [1, 9], [10, 2]]))
    # leader: p0, p1, p0 → two changes
    assert stats.lead_changes() == 2
