"""Preview URL and excerpt helpers for Google Docs cards."""

from __future__ import annotations


def build_preview_url(google_doc_id: str, width: int = 640, height: int = 480) -> str:
    doc_id = str(google_doc_id or "").strip()
    return f"https://drive.google.com/thumbnail?id={doc_id}&sz=w{width}-h{height}"


def build_excerpt(text: str | None, *, max_len: int = 240) -> str | None:
    if not text:
        return None
    collapsed = " ".join(str(text).split())
    if not collapsed:
        return None
    if len(collapsed) <= max_len:
        return collapsed
    return collapsed[: max_len - 1].rstrip() + "…"


def first_image_url(images: list[tuple[str, str | None]] | None) -> str | None:
    if not images:
        return None
    for src, _alt in images:
        src = str(src or "").strip()
        if src.startswith(("http://", "https://")):
            return src
    return None
