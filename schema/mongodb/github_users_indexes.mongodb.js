/**
 * MongoDB equivalent of schema/github_users_indexes.sql
 * Additional indexes on `github_users` (base table indexes).
 *
 *   mongosh "$MONGODB_URI" schema/mongodb/github_users_indexes.mongodb.js
 */

load("schema/mongodb/_common.mongodb.js");

print("Applying schema/mongodb/github_users_indexes.mongodb.js to " + mongoDbName());

// github_users
idx("github_users", { keys: {"id": 1}, "unique": true,"name": "github_users_id_unique" });
idx("github_users", { keys: {"login": 1}, "unique": true,"name": "github_users_login_unique" });
idx("github_users", { keys: {"country": 1}, "name": "github_users_country" });
idx("github_users", { keys: {"followers": -1}, "name": "github_users_followers" });
idx("github_users", { keys: {"last_scraped_at": -1}, "name": "github_users_last_scraped" });
idx("github_users", { keys: {"last_scraped_at": -1, "login": 1}, "name": "github_users_email_scraped","partialFilterExpression": {"email": {"$exists": true,"$type": "string","$gt": "" });
idx("github_users", { keys: {"followers": -1, "login": 1}, "name": "github_users_email_followers","partialFilterExpression": {"email": {"$exists": true,"$type": "string","$gt": "" });
idx("github_users", { keys: {"created_at": -1, "login": 1}, "name": "github_users_email_created","partialFilterExpression": {"email": {"$exists": true,"$type": "string","$gt": "" });
idx("github_users", { keys: {"login": 1}, "name": "github_users_email_login","partialFilterExpression": {"email": {"$exists": true,"$type": "string","$gt": "" });
idx("github_users", { keys: {"public_repos": -1, "login": 1}, "name": "github_users_email_repos","partialFilterExpression": {"email": {"$exists": true,"$type": "string","$gt": "" });
idx("github_users", { keys: {"country": 1, "last_scraped_at": -1}, "name": "github_users_country_email_scraped","partialFilterExpression": {"email": {"$exists": true,"$type": "string","$gt": "" });
idx("github_users", { keys: {"country": 1, "followers": -1}, "name": "github_users_country_email_followers","partialFilterExpression": {"email": {"$exists": true,"$type": "string","$gt": "" });
idx("github_users", { keys: {"country": 1, "created_at": -1}, "name": "github_users_country_email_created","partialFilterExpression": {"email": {"$exists": true,"$type": "string","$gt": "" });
idx("github_users", { keys: {"country": 1, "login": 1}, "name": "github_users_country_email_login","partialFilterExpression": {"email": {"$exists": true,"$type": "string","$gt": "" });
idx("github_users", { keys: {"login": text, "name": text, "email": text, "bio": text, "location": text, "country": text, "company": text}, "name": "github_users_text_search","default_language": "english" });

print("Done.");
