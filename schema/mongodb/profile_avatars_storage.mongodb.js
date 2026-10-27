/**
 * MongoDB equivalent of schema/profile_avatars_storage.sql
 * Postgres/Supabase Storage only — avatar files stored on disk or Supabase bucket, not MongoDB.
 *
 *   mongosh "$MONGODB_URI" schema/mongodb/profile_avatars_storage.mongodb.js
 */

load("schema/mongodb/_common.mongodb.js");

print("Applying schema/mongodb/profile_avatars_storage.mongodb.js to " + mongoDbName());

print("No MongoDB operations — Postgres/Supabase only. See schema/mongodb/README.md.");
