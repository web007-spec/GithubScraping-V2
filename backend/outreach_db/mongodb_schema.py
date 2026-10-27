"""MongoDB schema — indexes and validators (equivalent to schema/*.sql for Postgres)."""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

EMAIL_PRESENT = {"email": {"$exists": True, "$type": "string", "$gt": ""}}
CLIENT_MESSAGE_PRESENT = {
    "client_message_id": {"$exists": True, "$type": "string", "$gt": ""},
}


def _index_specs() -> list[tuple[str, list[dict[str, Any]]]]:
    """Return (collection_name, index_spec_list) for create_index calls."""
    return [
        (
            "github_users",
            [
                {"keys": [("id", 1)], "unique": True, "name": "github_users_id_unique"},
                {"keys": [("login", 1)], "unique": True, "name": "github_users_login_unique"},
                {"keys": [("country", 1)], "name": "github_users_country"},
                {"keys": [("followers", -1)], "name": "github_users_followers"},
                {"keys": [("last_scraped_at", -1)], "name": "github_users_last_scraped"},
                {
                    "keys": [("last_scraped_at", -1), ("login", 1)],
                    "partialFilterExpression": EMAIL_PRESENT,
                    "name": "github_users_email_scraped",
                },
                {
                    "keys": [("followers", -1), ("login", 1)],
                    "partialFilterExpression": EMAIL_PRESENT,
                    "name": "github_users_email_followers",
                },
                {
                    "keys": [("created_at", -1), ("login", 1)],
                    "partialFilterExpression": EMAIL_PRESENT,
                    "name": "github_users_email_created",
                },
                {
                    "keys": [("login", 1)],
                    "partialFilterExpression": EMAIL_PRESENT,
                    "name": "github_users_email_login",
                },
                {
                    "keys": [("public_repos", -1), ("login", 1)],
                    "partialFilterExpression": EMAIL_PRESENT,
                    "name": "github_users_email_repos",
                },
                {
                    "keys": [("country", 1), ("last_scraped_at", -1)],
                    "partialFilterExpression": EMAIL_PRESENT,
                    "name": "github_users_country_email_scraped",
                },
                {
                    "keys": [("country", 1), ("followers", -1)],
                    "partialFilterExpression": EMAIL_PRESENT,
                    "name": "github_users_country_email_followers",
                },
                {
                    "keys": [("country", 1), ("created_at", -1)],
                    "partialFilterExpression": EMAIL_PRESENT,
                    "name": "github_users_country_email_created",
                },
                {
                    "keys": [("country", 1), ("login", 1)],
                    "partialFilterExpression": EMAIL_PRESENT,
                    "name": "github_users_country_email_login",
                },
                {
                    "keys": [
                        ("login", "text"),
                        ("name", "text"),
                        ("email", "text"),
                        ("bio", "text"),
                        ("location", "text"),
                        ("country", "text"),
                        ("company", "text"),
                    ],
                    "name": "github_users_text_search",
                    "default_language": "english",
                },
            ],
        ),
        (
            "github_user_country_stats",
            [
                {"keys": [("country", 1)], "unique": True, "name": "country_stats_country_unique"},
                {"keys": [("user_count", -1)], "name": "country_stats_count"},
            ],
        ),
        (
            "scraping_runs",
            [
                {"keys": [("id", 1)], "unique": True, "name": "scraping_runs_id_unique"},
                {"keys": [("status", 1), ("created_at", -1)], "name": "scraping_runs_status_created"},
            ],
        ),
        (
            "github_tokens",
            [
                {"keys": [("id", 1)], "unique": True, "name": "github_tokens_id_unique"},
                {"keys": [("is_active", 1)], "name": "github_tokens_active"},
            ],
        ),
        (
            "scheduled_jobs",
            [
                {"keys": [("id", 1)], "unique": True, "name": "scheduled_jobs_id_unique"},
                {"keys": [("active", 1), ("next_run_at", 1)], "name": "scheduled_jobs_active_next"},
            ],
        ),
        (
            "google_documents",
            [
                {"keys": [("google_doc_id", 1)], "unique": True, "name": "google_documents_doc_id_unique"},
                {"keys": [("status", 1), ("crawled_at", -1)], "name": "google_documents_status_crawled"},
                {"keys": [("status", 1), ("content_archived_at", -1)], "name": "google_documents_status_archived"},
                {"keys": [("title", 1)], "name": "google_documents_title"},
                {"keys": [("word_count", -1)], "name": "google_documents_word_count"},
                {"keys": [("shared_by_email", 1)], "name": "google_documents_shared_by_email"},
                {"keys": [("shared_at", -1)], "name": "google_documents_shared_at"},
                {
                    "keys": [("title", "text"), ("excerpt", "text"), ("search_text", "text"), ("headings", "text")],
                    "name": "google_documents_text_search",
                    "default_language": "english",
                    "language_override": "doc_language",
                },
            ],
        ),
        (
            "google_docs_crawl_runs",
            [
                {"keys": [("id", 1)], "unique": True, "name": "google_docs_crawl_runs_id_unique"},
                {"keys": [("status", 1), ("created_at", -1)], "name": "google_docs_crawl_runs_status_created"},
            ],
        ),
        (
            "google_drive_folders",
            [
                {"keys": [("folder_id", 1)], "unique": True, "name": "google_drive_folders_id_unique"},
                {"keys": [("parent_folder_id", 1)], "name": "google_drive_folders_parent"},
                {"keys": [("crawled_at", -1)], "name": "google_drive_folders_crawled"},
            ],
        ),
        (
            "google_drive_files",
            [
                {"keys": [("file_id", 1)], "unique": True, "name": "google_drive_files_id_unique"},
                {"keys": [("folder_id", 1)], "name": "google_drive_files_folder"},
                {"keys": [("mime_type", 1)], "name": "google_drive_files_mime"},
                {"keys": [("extension", 1)], "name": "google_drive_files_extension"},
                {"keys": [("modified_time", -1)], "name": "google_drive_files_modified"},
                {"keys": [("sha256", 1)], "name": "google_drive_files_sha256"},
                {"keys": [("md5", 1)], "name": "google_drive_files_md5"},
                {"keys": [("status", 1), ("indexed_at", -1)], "name": "google_drive_files_status_indexed"},
                {"keys": [("categories", 1)], "name": "google_drive_files_categories"},
                {
                    "keys": [("name", "text"), ("search_text", "text"), ("raw_text", "text"), ("description", "text")],
                    "name": "google_drive_files_text_search",
                    "default_language": "english",
                },
            ],
        ),
        (
            "google_drive_crawl_runs",
            [
                {"keys": [("id", 1)], "unique": True, "name": "google_drive_crawl_runs_id_unique"},
                {"keys": [("status", 1), ("created_at", -1)], "name": "google_drive_crawl_runs_status_created"},
            ],
        ),
        (
            "extension_contacts",
            [
                {"keys": [("id", 1)], "unique": True, "name": "extension_contacts_id_unique"},
                {"keys": [("github_login", 1)], "unique": True, "name": "extension_contacts_login_unique"},
                {"keys": [("owner_ip", 1), ("added_at", -1)], "name": "extension_contacts_owner_added"},
                {"keys": [("email", 1)], "name": "extension_contacts_email"},
            ],
        ),
        (
            "extension_join_requests",
            [
                {"keys": [("id", 1)], "unique": True, "name": "extension_join_requests_id_unique"},
                {"keys": [("owner_ip", 1)], "unique": True, "name": "extension_join_requests_owner_ip_unique"},
                {"keys": [("status", 1), ("requested_at", -1)], "name": "extension_join_requests_status"},
            ],
        ),
        (
            "extension_ai_access_requests",
            [
                {"keys": [("id", 1)], "unique": True, "name": "extension_ai_access_id_unique"},
            ],
        ),
        (
            "registration_ip_locks",
            [
                {"keys": [("id", 1)], "unique": True, "name": "registration_ip_locks_id_unique"},
                {"keys": [("owner_ip", 1)], "unique": True, "name": "registration_ip_locks_owner_ip_unique"},
                {"keys": [("created_at", -1)], "name": "registration_ip_locks_created"},
            ],
        ),
        (
            "app_releases",
            [
                {"keys": [("id", 1)], "unique": True, "name": "app_releases_id_unique"},
                {"keys": [("storage_path", 1)], "unique": True, "name": "app_releases_storage_path_unique"},
                {"keys": [("created_at", -1)], "name": "app_releases_created_at"},
                {
                    "keys": [("is_example", 1)],
                    "unique": True,
                    "partialFilterExpression": {"is_example": True},
                    "name": "app_releases_single_example",
                },
            ],
        ),
        (
            "chat_conversations",
            [
                {"keys": [("id", 1)], "unique": True, "name": "chat_conversations_id_unique"},
                {"keys": [("last_message_at", -1)], "name": "chat_conversations_last_message"},
                {
                    "keys": [("slug", 1)],
                    "unique": True,
                    "name": "chat_conversations_slug_unique",
                    "partialFilterExpression": {"slug": {"$type": "string"}},
                },
            ],
        ),
        (
            "chat_members",
            [
                {
                    "keys": [("conversation_id", 1), ("user_id", 1)],
                    "unique": True,
                    "name": "chat_members_conv_user_unique",
                },
                {"keys": [("user_id", 1)], "name": "chat_members_user"},
            ],
        ),
        (
            "chat_messages",
            [
                {"keys": [("id", 1)], "unique": True, "name": "chat_messages_id_unique"},
                {"keys": [("conversation_id", 1), ("created_at", -1)], "name": "chat_messages_conv_created"},
                {"keys": [("client_message_id", 1)], "sparse": True, "name": "chat_messages_client_message_id"},
                {
                    "keys": [("conversation_id", 1), ("sender_id", 1), ("client_message_id", 1)],
                    "unique": True,
                    "partialFilterExpression": CLIENT_MESSAGE_PRESENT,
                    "name": "chat_messages_client_dedupe",
                },
                {"keys": [("reply_to_id", 1)], "sparse": True, "name": "chat_messages_reply_to"},
            ],
        ),
        (
            "chat_typing",
            [
                {
                    "keys": [("conversation_id", 1), ("user_id", 1)],
                    "unique": True,
                    "name": "chat_typing_conv_user_unique",
                },
            ],
        ),
        (
            "chat_direct_pairs",
            [
                {"keys": [("user_a", 1), ("user_b", 1)], "unique": True, "name": "chat_direct_pairs_unique"},
            ],
        ),
        (
            "chat_presence",
            [
                {"keys": [("user_id", 1)], "unique": True, "name": "chat_presence_user_unique"},
            ],
        ),
        (
            "chat_reactions",
            [
                {
                    "keys": [("message_id", 1), ("user_id", 1), ("emoji", 1)],
                    "unique": True,
                    "name": "chat_reactions_unique",
                },
            ],
        ),
        (
            "chat_message_unlocks",
            [
                {"keys": [("id", 1)], "unique": True, "name": "chat_message_unlocks_id_unique"},
                {
                    "keys": [("message_id", 1), ("user_id", 1)],
                    "unique": True,
                    "name": "chat_message_unlocks_msg_user_unique",
                },
                {"keys": [("user_id", 1)], "name": "chat_message_unlocks_user"},
            ],
        ),
        (
            "auth_users",
            [
                {"keys": [("id", 1)], "unique": True, "name": "auth_users_id_unique"},
                {"keys": [("email", 1)], "unique": True, "name": "auth_users_email_unique"},
            ],
        ),
    ]


def apply_schema(db) -> dict[str, int]:
    """Create all collection indexes. Safe to run multiple times."""
    counts: dict[str, int] = {}
    for collection_name, specs in _index_specs():
        col = db[collection_name]
        created = 0
        existing = col.index_information()
        existing_keys = {
            tuple(v["key"]) for name, v in existing.items() if name != "_id_"
        }
        for spec in specs:
            options = dict(spec)
            keys = options.pop("keys")
            name = options.get("name")
            key_tuple = tuple(keys)
            if name in existing:
                continue
            if key_tuple in existing_keys:
                continue
            try:
                col.create_index(keys, **options)
                created += 1
                existing_keys.add(key_tuple)
            except Exception as exc:
                code = getattr(exc, "code", None)
                if code == 85 or "already exists with a different name" in str(exc):
                    continue
                log.warning("Index %s.%s failed: %s", collection_name, name, exc)
        counts[collection_name] = created
    return counts


def rebuild_country_stats(db) -> int:
    """Equivalent to rebuild_github_user_country_stats() SQL function."""
    users = db.github_users
    stats = db.github_user_country_stats
    pipeline = [
        {"$match": {"country": {"$exists": True, "$ne": None, "$ne": ""}, "email": {"$exists": True, "$ne": None, "$ne": ""}}},
        {"$group": {"_id": "$country", "user_count": {"$sum": 1}}},
    ]
    rows = list(users.aggregate(pipeline))
    stats.delete_many({})
    if not rows:
        return 0
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    docs = [{"country": row["_id"], "user_count": row["user_count"], "updated_at": now} for row in rows]
    stats.insert_many(docs)
    return len(docs)


def ensure_indexes() -> None:
    from outreach_db.client import get_database

    apply_schema(get_database())
