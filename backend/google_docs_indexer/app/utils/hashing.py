"""SHA256 hashing utilities."""

import hashlib


def compute_sha256(content: str | bytes) -> str:
    """Compute SHA256 hex digest of content."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()
