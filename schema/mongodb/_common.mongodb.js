/**
 * Shared helpers for schema/mongodb/*.mongodb.js modules.
 * Usage: load('schema/mongodb/_common.mongodb.js');
 */

function mongoDbName() {
  if (typeof process !== "undefined" && process.env.MONGODB_DB) {
    return process.env.MONGODB_DB;
  }
  return "outreach_console";
}

function mongoDb() {
  return db.getSiblingDB(mongoDbName());
}

const emailPresent = { email: { $exists: true, $type: "string", $gt: "" } };

function idx(col, spec) {
  const mdb = mongoDb();
  const keys = spec.keys;
  const opts = { ...spec };
  delete opts.keys;
  try {
    mdb.getCollection(col).createIndex(keys, opts);
    print(`  OK ${col}.${opts.name || JSON.stringify(keys)}`);
  } catch (e) {
    print(`  skip ${col}.${opts.name}: ${e.message}`);
  }
}

function rebuildCountryStats() {
  const mdb = mongoDb();
  const rows = mdb.github_users.aggregate([
    {
      $match: {
        country: { $exists: true, $ne: null, $ne: "" },
        email: { $exists: true, $ne: null, $ne: "" },
      },
    },
    { $group: { _id: "$country", user_count: { $sum: 1 } } },
  ]).toArray();
  mdb.github_user_country_stats.deleteMany({});
  if (rows.length) {
    mdb.github_user_country_stats.insertMany(
      rows.map((r) => ({ country: r._id, user_count: r.user_count, updated_at: new Date() }))
    );
  }
  print(`Rebuilt github_user_country_stats: ${rows.length} countries`);
  return rows.length;
}
