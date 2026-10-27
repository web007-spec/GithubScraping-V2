"""Pytest configuration — keep google_docs_indexer `app` isolated from github_Scraping."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

INDEXER_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = INDEXER_ROOT.parent


def _prepend(path: Path) -> None:
    s = str(path)
    while s in sys.path:
        sys.path.remove(s)
    sys.path.insert(0, s)


def _purge_app_modules() -> None:
    indexer = str(INDEXER_ROOT).replace("\\", "/").lower()
    for key in list(sys.modules):
        if key != "app" and not key.startswith("app."):
            continue
        mod = sys.modules.get(key)
        mod_file = getattr(mod, "__file__", "") or ""
        if mod_file and indexer not in mod_file.replace("\\", "/").lower():
            del sys.modules[key]


def _sanitize_sys_path() -> None:
    cleaned: list[str] = []
    for entry in sys.path:
        norm = entry.replace("\\", "/").lower()
        if "google docs scraping" in norm:
            continue
        cleaned.append(entry)
    sys.path[:] = cleaned


def _purge_tests_modules() -> None:
    indexer_tests = str(INDEXER_ROOT / "tests").replace("\\", "/").lower()
    for key in list(sys.modules):
        if key != "tests" and not key.startswith("tests."):
            continue
        mod = sys.modules.get(key)
        mod_file = getattr(mod, "__file__", "") or ""
        if mod_file and indexer_tests not in mod_file.replace("\\", "/").lower():
            del sys.modules[key]


def pytest_configure() -> None:
    _sanitize_sys_path()
    _prepend(BACKEND_ROOT)
    _prepend(INDEXER_ROOT)
    _purge_app_modules()
    _purge_tests_modules()


@pytest.fixture(autouse=True)
def _isolate_indexer_app_package() -> None:
    _prepend(INDEXER_ROOT)
    _purge_app_modules()
    _purge_tests_modules()


@pytest.fixture
def sample_html() -> str:
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Sample Document</title></head>
    <body>
        <h1>Main Heading</h1>
        <p>First paragraph with <a href="https://example.com">a link</a>.</p>
        <ul><li>Item one</li><li>Item two</li></ul>
        <table><tr><td>Cell A</td><td>Cell B</td></tr></table>
        <img src="https://example.com/image.png" alt="Sample image">
        <h2>Subheading</h2>
        <p>Second paragraph here.</p>
    </body>
    </html>
    """
