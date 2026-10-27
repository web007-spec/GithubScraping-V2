"""MongoDB equivalents of Supabase SQL functions."""

from __future__ import annotations

from datetime import datetime, timezone

from outreach_db.client import get_database


def rebuild_github_user_country_stats() -> None:
    db = get_database()
    users = db.github_users
    stats = db.github_user_country_stats

    pipeline = [
        {"$match": {"country": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$country", "user_count": {"$sum": 1}}},
    ]
    counts = {row["_id"]: int(row["user_count"]) for row in users.aggregate(pipeline)}
    now = datetime.now(timezone.utc).isoformat()

    for country, count in counts.items():
        stats.update_one(
            {"country": country},
            {"$set": {"country": country, "user_count": count, "updated_at": now}},
            upsert=True,
        )

    if counts:
        stats.delete_many({"country": {"$nin": list(counts.keys())}})
    else:
        stats.delete_many({})
