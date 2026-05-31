"""Tests for the grader scoring — including reward-rebalance invariance."""

from staghunt_tools.episode import from_results
from staghunt_tools.grader import grade_episode

from test_episode import build_results


def test_boring_solo_episode_scores_low():
    # 4 players each soloing rabbits, equal scores.
    results = build_results(4, [(0, [i]) for i in range(4) for _ in range(3)], scores=[3, 3, 3, 3])
    grade = grade_episode(from_results(results))
    assert grade.components["cooperation_depth"] == 0.0
    assert grade.components["cooperation_breadth"] == 0.0
    assert grade.components["prey_diversity"] == 0.0
    assert grade.score < 0.35


def test_coordinated_bigfame_episode_scores_high():
    # 4 players repeatedly taking elephants (kind 4) and moose (kind 3) together,
    # plus some variety, with a competitive spread of scores.
    captures = (
        [(4, [0, 1, 2, 3])] * 3
        + [(3, [0, 1, 2])] * 2
        + [(2, [1, 3])] * 2
        + [(0, [0]), (1, [2])]
    )
    results = build_results(4, captures, scores=[40, 35, 30, 28])
    grade = grade_episode(from_results(results))
    assert grade.components["cooperation_depth"] > 0.5
    assert grade.components["cooperation_breadth"] == 1.0
    assert grade.components["prey_diversity"] > 0.5
    assert grade.score > 0.6


def test_interesting_beats_boring():
    boring = grade_episode(from_results(build_results(4, [(0, [i]) for i in range(4)], scores=[1, 1, 1, 1])))
    coordinated = grade_episode(
        from_results(build_results(4, [(4, [0, 1, 2, 3])] * 4, scores=[20, 18, 16, 14]))
    )
    assert coordinated.score > boring.score


def test_reward_rebalance_invariance():
    """Scaling every score by a constant (as a points rebalance would) must not
    move the grade: coordination/diversity ignore scores, and balance uses a
    scale-invariant Gini."""
    captures = [(4, [0, 1, 2, 3])] * 2 + [(2, [0, 1])] + [(0, [2])]
    base = grade_episode(from_results(build_results(4, captures, scores=[10, 8, 5, 3])))
    rescaled = grade_episode(from_results(build_results(4, captures, scores=[100, 80, 50, 30])))
    assert base.components == rescaled.components
    assert base.score == rescaled.score


def test_relabel_points_does_not_change_coordination_components():
    """Same captures, totally different score *distribution* — the coordination
    components are unaffected; only balance may move."""
    captures = [(4, [0, 1, 2, 3])] * 2 + [(3, [0, 1, 2])]
    a = grade_episode(from_results(build_results(4, captures, scores=[5, 5, 5, 5])))
    b = grade_episode(from_results(build_results(4, captures, scores=[50, 1, 1, 1])))
    assert a.components["cooperation_depth"] == b.components["cooperation_depth"]
    assert a.components["cooperation_breadth"] == b.components["cooperation_breadth"]
    assert a.components["prey_diversity"] == b.components["prey_diversity"]


def test_score_bounds():
    grade = grade_episode(from_results(build_results(4, [(4, [0, 1, 2, 3])] * 10, scores=[9, 9, 9, 9])))
    assert 0.0 <= grade.score <= 1.0
