"""Public Drive content categories — shared by API and crawl worker."""

from __future__ import annotations

from typing import Any

MIME_GOOGLE_DOC = "application/vnd.google-apps.document"
MIME_GOOGLE_SHEET = "application/vnd.google-apps.spreadsheet"
MIME_GOOGLE_SLIDE = "application/vnd.google-apps.presentation"
MIME_PDF = "application/pdf"
MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MIME_PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
MIME_CSV = "text/csv"
MIME_TXT = "text/plain"
MIME_HTML = "text/html"
MIME_JSON = "application/json"

CATEGORY_TREE: list[dict[str, Any]] = [
    {
        "id": "research_papers",
        "label": "Research papers",
        "description": "Scientific and academic publications",
        "subcategories": [
            {"id": "ai", "label": "AI"},
            {"id": "medicine", "label": "Medicine"},
            {"id": "biology", "label": "Biology"},
            {"id": "physics", "label": "Physics"},
        ],
        "mime_types": [MIME_PDF, MIME_GOOGLE_DOC, MIME_DOCX],
        "extensions": {".pdf", ".docx", ".doc"},
    },
    {
        "id": "manuals",
        "label": "Manuals",
        "description": "User guides and technical documentation",
        "subcategories": [
            {"id": "user_guides", "label": "User guides"},
            {"id": "technical_docs", "label": "Technical documentation"},
            {"id": "api_docs", "label": "API documentation"},
        ],
        "mime_types": [MIME_PDF, MIME_GOOGLE_DOC, MIME_HTML, MIME_DOCX],
        "extensions": {".pdf", ".docx", ".html", ".htm"},
    },
    {
        "id": "books",
        "label": "Books",
        "description": "Public domain and educational books",
        "subcategories": [
            {"id": "public_domain", "label": "Public domain books"},
            {"id": "educational", "label": "Educational materials"},
        ],
        "mime_types": [MIME_PDF, MIME_GOOGLE_DOC, MIME_DOCX],
        "extensions": {".pdf", ".epub", ".docx"},
    },
    {
        "id": "company_documents",
        "label": "Company documents",
        "description": "Whitepapers, reports, product docs",
        "subcategories": [
            {"id": "whitepapers", "label": "Whitepapers"},
            {"id": "public_reports", "label": "Public reports"},
            {"id": "product_docs", "label": "Product documentation"},
        ],
        "mime_types": [MIME_PDF, MIME_GOOGLE_DOC, MIME_GOOGLE_SLIDE, MIME_PPTX],
        "extensions": {".pdf", ".pptx", ".docx"},
    },
    {
        "id": "university_materials",
        "label": "University materials",
        "description": "Lecture notes, courses, assignments",
        "subcategories": [
            {"id": "lecture_notes", "label": "Lecture notes"},
            {"id": "course_materials", "label": "Course materials"},
            {"id": "assignments", "label": "Assignments"},
            {"id": "presentations", "label": "Presentations"},
        ],
        "mime_types": [MIME_PDF, MIME_GOOGLE_DOC, MIME_GOOGLE_SLIDE, MIME_GOOGLE_SHEET],
        "extensions": {".pdf", ".pptx", ".docx", ".xlsx"},
    },
    {
        "id": "government_publications",
        "label": "Government publications",
        "description": "Reports, statistics, regulations",
        "subcategories": [
            {"id": "reports", "label": "Reports"},
            {"id": "statistics", "label": "Statistics"},
            {"id": "regulations", "label": "Regulations"},
        ],
        "mime_types": [MIME_PDF, MIME_CSV, MIME_XLSX, MIME_GOOGLE_SHEET],
        "extensions": {".pdf", ".csv", ".xlsx"},
    },
    {
        "id": "templates",
        "label": "Templates",
        "description": "Business plans, resumes, contracts, spreadsheets",
        "subcategories": [
            {"id": "business_plans", "label": "Business plans"},
            {"id": "resumes", "label": "Resumes"},
            {"id": "contracts", "label": "Contracts"},
            {"id": "spreadsheets", "label": "Spreadsheets"},
        ],
        "mime_types": [MIME_GOOGLE_DOC, MIME_GOOGLE_SHEET, MIME_DOCX, MIME_XLSX],
        "extensions": {".docx", ".xlsx", ".xls", ".ods"},
    },
    {
        "id": "images",
        "label": "Images",
        "description": "Logos, diagrams, charts, illustrations",
        "subcategories": [
            {"id": "logos", "label": "Logos"},
            {"id": "diagrams", "label": "Diagrams"},
            {"id": "charts", "label": "Charts"},
            {"id": "illustrations", "label": "Educational illustrations"},
        ],
        "mime_prefixes": ["image/"],
        "extensions": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"},
    },
    {
        "id": "pdfs",
        "label": "PDFs",
        "description": "Scientific articles, financial reports, catalogs",
        "subcategories": [
            {"id": "scientific_articles", "label": "Scientific articles"},
            {"id": "financial_reports", "label": "Financial reports"},
            {"id": "product_catalogs", "label": "Product catalogs"},
        ],
        "mime_types": [MIME_PDF],
        "extensions": {".pdf"},
    },
]


def flatten_categories(selected: list[str]) -> set[str]:
    return {str(item).strip().lower() for item in selected if str(item).strip()}


def resolve_allowed_mime_and_extensions(selected: list[str]) -> tuple[set[str], set[str], set[str]]:
    picked = flatten_categories(selected)
    if not picked:
        all_mimes: set[str] = set()
        all_prefixes: set[str] = set()
        all_ext: set[str] = set()
        for cat in CATEGORY_TREE:
            all_mimes.update(cat.get("mime_types") or [])
            all_prefixes.update(cat.get("mime_prefixes") or [])
            all_ext.update(cat.get("extensions") or set())
        return all_mimes, all_prefixes, all_ext

    mimes: set[str] = set()
    prefixes: set[str] = set()
    extensions: set[str] = set()
    for cat in CATEGORY_TREE:
        cat_id = cat["id"]
        subs = {s["id"] for s in cat.get("subcategories") or []}
        if cat_id in picked or picked.intersection(subs):
            mimes.update(cat.get("mime_types") or [])
            prefixes.update(cat.get("mime_prefixes") or [])
            extensions.update(cat.get("extensions") or set())
    return mimes, prefixes, extensions


def file_matches_categories(
    *,
    mime_type: str,
    extension: str,
    selected: list[str],
    name: str = "",
) -> bool:
    if not selected:
        return True

    mimes, prefixes, extensions = resolve_allowed_mime_and_extensions(selected)
    ext = (extension or "").lower()
    if ext and not ext.startswith("."):
        ext = f".{ext}"
    mime = (mime_type or "").lower()

    if not mime and not ext:
        # Type unknown until download — allow probe; filtered again after download.
        return True

    if mime and mime in {m.lower() for m in mimes}:
        return True
    if mime and any(mime.startswith(p.lower()) for p in prefixes):
        return True
    if ext and ext in {e.lower() for e in extensions}:
        return True

    lower_name = (name or "").lower()
    if lower_name and any(lower_name.endswith(e) for e in extensions):
        return True

    return False


def categories_for_api() -> list[dict[str, Any]]:
    return CATEGORY_TREE
