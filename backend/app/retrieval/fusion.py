from collections import defaultdict
from collections.abc import Hashable, Sequence


def reciprocal_rank_fusion[T: Hashable](
    rankings: Sequence[Sequence[T]], k: int = 60
) -> list[tuple[T, float]]:
    """Merge ranked id lists into one, best first.

    Fuses ranks rather than scores: cosine similarity and `ts_rank_cd` live on unrelated
    scales. Ties keep first-seen order, so the result is deterministic.
    """
    scores: dict[T, float] = defaultdict(float)
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda pair: -pair[1])
