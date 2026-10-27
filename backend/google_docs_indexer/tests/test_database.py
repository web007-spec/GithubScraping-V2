"""Integration tests (require PostgreSQL)."""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL") and not os.getenv("TEST_DATABASE"),
    reason="DATABASE_URL or TEST_DATABASE not set",
)
