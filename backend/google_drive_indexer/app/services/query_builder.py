"""Build web-search queries from selected Drive content categories."""

from __future__ import annotations

from pathlib import Path

from google_drive_db.categories import CATEGORY_TREE, flatten_categories


def queries_for_categories(selected: list[str]) -> list[str]:
    """Generate search phrases from category and subcategory labels."""
    picked = flatten_categories(selected)
    if not picked:
        return []

    queries: list[str] = []
    seen: set[str] = set()

    def add(query: str) -> None:
        q = query.strip()
        if not q:
            return
        key = q.lower()
        if key in seen:
            return
        seen.add(key)
        queries.append(q)

    for cat in CATEGORY_TREE:
        cat_id = cat["id"]
        subs = cat.get("subcategories") or []
        sub_ids = {s["id"] for s in subs}
        cat_selected = cat_id in picked or bool(picked.intersection(sub_ids))
        if not cat_selected:
            continue

        add(str(cat.get("label") or cat_id))
        add(f"public {cat.get('label') or cat_id}")
        for sub in subs:
            sub_id = sub["id"]
            if sub_id in picked or cat_id in picked:
                label = str(sub.get("label") or sub_id)
                add(label)
                add(f"{cat.get('label') or cat_id} {label}")

    return queries


def merge_query_sources(
    *,
    categories: list[str],
    queries_file: Path | None = None,
) -> list[str]:
    """Category-specific queries first; fall back to queries.txt when none."""
    from app.services.batch_search_service import BatchSearchService

    category_queries = queries_for_categories(categories)
    if category_queries:
        return category_queries

    if queries_file and queries_file.exists():
        return BatchSearchService.load_queries(queries_file)

    return []
