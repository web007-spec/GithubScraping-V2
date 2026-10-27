/**
 * MongoDB equivalent of schema/country_stats.sql
 * Collection `github_user_country_stats` — run rebuildCountryStats() instead of SQL triggers.
 *
 *   mongosh "$MONGODB_URI" schema/mongodb/country_stats.mongodb.js
 */

load("schema/mongodb/_common.mongodb.js");

print("Applying schema/mongodb/country_stats.mongodb.js to " + mongoDbName());

// github_user_country_stats
idx("github_user_country_stats", { keys: {"country": 1}, "unique": true,"name": "country_stats_country_unique" });
idx("github_user_country_stats", { keys: {"user_count": -1}, "name": "country_stats_count" });

// Replaces SQL rebuild_github_user_country_stats() + trigger
rebuildCountryStats();

print("Done.");
