/**
 * MongoDB equivalent of schema/extension_anon_read.sql
 * Postgres-only: RLS policies for anonymous read. Enforced in application code for MongoDB.
 *
 *   mongosh "$MONGODB_URI" schema/mongodb/extension_anon_read.mongodb.js
 */

load("schema/mongodb/_common.mongodb.js");

print("Applying schema/mongodb/extension_anon_read.mongodb.js to " + mongoDbName());

print("No MongoDB operations — Postgres/Supabase only. See schema/mongodb/README.md.");
