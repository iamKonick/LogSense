"""Reproducible lexical vector baseline, explicitly not semantic embeddings."""

from sklearn.feature_extraction.text import HashingVectorizer

DIMENSIONS = 384
vectorizer = HashingVectorizer(
    n_features=DIMENSIONS,
    alternate_sign=False,
    ngram_range=(1, 2),
    norm="l2",
    stop_words="english",
)


def embed(text: str) -> list[float]:
    return vectorizer.transform([text]).toarray()[0].tolist()


def vector_literal(text: str) -> str:
    return "[" + ",".join(str(x) for x in embed(text)) + "]"
