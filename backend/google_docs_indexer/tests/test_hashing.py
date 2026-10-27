"""Hashing and duplicate detection tests."""

from app.utils.hashing import compute_sha256


def test_sha256_consistent():
    h1 = compute_sha256("same content")
    h2 = compute_sha256("same content")
    assert h1 == h2
    assert len(h1) == 64


def test_sha256_different_content():
    h1 = compute_sha256("content a")
    h2 = compute_sha256("content b")
    assert h1 != h2
