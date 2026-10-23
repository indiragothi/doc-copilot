import pytest

from app.retrieval.fusion import reciprocal_rank_fusion


def test_item_in_both_rankings_beats_items_in_one():
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["d", "c"]])

    assert fused[0][0] == "c"


def test_score_is_sum_of_reciprocal_ranks():
    fused = dict(reciprocal_rank_fusion([["a", "b"], ["b"]], k=60))

    assert fused["a"] == pytest.approx(1 / 61)
    assert fused["b"] == pytest.approx(1 / 62 + 1 / 61)


def test_ties_keep_first_seen_order():
    fused = reciprocal_rank_fusion([["a"], ["b"]])

    assert [item for item, _ in fused] == ["a", "b"]


def test_empty_rankings_give_empty_result():
    assert reciprocal_rank_fusion([[], []]) == []
    assert reciprocal_rank_fusion([]) == []
