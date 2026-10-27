/**
 * MongoDB equivalent of schema/fix_github_users_identity_conflicts.sql
 * Postgres-only: dedupe conflicting login/id rows. MongoDB uses unique indexes on id and login.
 *
 *   mongosh "$MONGODB_URI" schema/mongodb/fix_github_users_identity_conflicts.mongodb.js
 */

load("schema/mongodb/_common.mongodb.js");

print("Applying schema/mongodb/fix_github_users_identity_conflicts.mongodb.js to " + mongoDbName());

print("No MongoDB operations — Postgres/Supabase only. See schema/mongodb/README.md.");
