/**
 * MongoDB equivalent of schema/extension_contacts.sql
 * Collection `extension_contacts`.
 *
 *   mongosh "$MONGODB_URI" schema/mongodb/extension_contacts.mongodb.js
 */

load("schema/mongodb/_common.mongodb.js");

print("Applying schema/mongodb/extension_contacts.mongodb.js to " + mongoDbName());

// extension_contacts
idx("extension_contacts", { keys: {"id": 1}, "unique": true,"name": "extension_contacts_id_unique" });
idx("extension_contacts", { keys: {"github_login": 1}, "unique": true,"name": "extension_contacts_login_unique" });
idx("extension_contacts", { keys: {"owner_ip": 1, "added_at": -1}, "name": "extension_contacts_owner_added" });
idx("extension_contacts", { keys: {"email": 1}, "name": "extension_contacts_email" });

print("Done.");
