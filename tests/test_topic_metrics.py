import numpy as np

from src.classify.metrics import (
    clustering_scores,
    compare_cluster_counts,
    content_terms,
    keyword_matches,
    label_agreement,
)


def _two_groups() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(0)
    left = rng.normal(loc=-2.0, scale=0.05, size=(30, 8))
    right = rng.normal(loc=2.0, scale=0.05, size=(30, 8))
    vectors = np.vstack([left, right])
    labels = np.array([0] * 30 + [1] * 30)
    return vectors, labels


def test_separated_groups_score_higher_than_a_random_split():
    vectors, labels = _two_groups()
    good = clustering_scores(vectors, labels)
    shuffled = clustering_scores(vectors, np.array(([0, 1] * 30)))
    assert good["silhouette_cosine"] > 0.5
    assert good["silhouette_cosine"] > shuffled["silhouette_cosine"]
    assert good["mean_cosine_to_centroid"] > shuffled["mean_cosine_to_centroid"]
    assert good["davies_bouldin"] < shuffled["davies_bouldin"]
    assert good["sizes"] == {0: 30, 1: 30}


def test_compare_cluster_counts_keeps_each_k():
    vectors, _labels = _two_groups()
    rows = compare_cluster_counts(vectors, [2, 4], n_init=5)
    assert [row["k"] for row in rows] == [2, 4]
    assert rows[0]["silhouette_cosine"] > rows[1]["silhouette_cosine"]


def test_keyword_agreement_ignores_stopwords_in_the_name():
    assert content_terms("the / Poland / education") == ["poland", "education"]
    assert keyword_matches(["Education policy"], ["education"])
    assert not keyword_matches(["quantum optics"], ["education"])
    report = label_agreement(
        [["education policy"], ["quantum optics"], []],
        np.array([0, 0, 1]),
        {0: "the / education", 1: "and / the"},
    )
    assert report["hit_rate"] == 0.5
    assert report["papers_without_keywords"] == 1
    assert report["per_cluster"][1]["hit_rate"] is None
