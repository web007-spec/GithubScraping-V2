/**
 * MongoDB equivalent of schema/google_documents.sql
 * Collection `google_documents`.
 *
 *   mongosh "$MONGODB_URI" schema/mongodb/google_documents.mongodb.js
 */

load("schema/mongodb/_common.mongodb.js");

print("Applying schema/mongodb/google_documents.mongodb.js to " + mongoDbName());

// google_documents
idx("google_documents", { keys: {"google_doc_id": 1}, "unique": true,"name": "google_documents_doc_id_unique" });
idx("google_documents", { keys: {"status": 1, "crawled_at": -1}, "name": "google_documents_status_crawled" });
idx("google_documents", { keys: {"status": 1, "content_archived_at": -1}, "name": "google_documents_status_archived" });
idx("google_documents", { keys: {"title": 1}, "name": "google_documents_title" });
idx("google_documents", { keys: {"word_count": -1}, "name": "google_documents_word_count" });
idx("google_documents", { keys: {"shared_by_email": 1}, "name": "google_documents_shared_by_email" });
idx("google_documents", { keys: {"shared_at": -1}, "name": "google_documents_shared_at" });
idx("google_documents", { keys: {"title": text, "excerpt": text, "search_text": text, "headings": text}, "name": "google_documents_text_search","default_language": "english" });

print("Done.");
