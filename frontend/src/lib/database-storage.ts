/** True when app data is stored in MongoDB (not Supabase Postgres). Auth still uses Supabase. */
export const useMongoStorage =
  process.env.NEXT_PUBLIC_DATABASE_STORAGE === "mongodb" ||
  process.env.NEXT_PUBLIC_USE_MONGODB === "true";
