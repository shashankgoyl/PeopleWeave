import { openDB } from "idb";

// Zero-setup local fallback so `npm run dev` works immediately with no
// Supabase project configured - mirrors the old Flask app's local.db SQLite
// fallback, just in the browser instead of on a server. Audio blobs and
// submission rows both live in IndexedDB; nothing leaves the machine.

const DB_NAME = "peopleweave_local";
const DB_VERSION = 1;

function getDb() {
  return openDB(DB_NAME, DB_VERSION, {
    upgrade(db) {
      db.createObjectStore("people", { keyPath: "id" });
      db.createObjectStore("audio_submissions", { keyPath: "id" });
    },
  });
}

function normalizePhone10(phone) {
  const digits = String(phone).replace(/\D/g, "");
  const stripped = digits.length > 10 && digits.startsWith("91") ? digits.slice(2) : digits;
  return stripped.length >= 10 ? stripped.slice(-10) : stripped || null;
}

export async function localFindOrCreatePerson(name, phone) {
  const db = await getDb();
  const normPhone = normalizePhone10(phone);
  const all = await db.getAll("people");
  const existing = normPhone ? all.find((p) => p.primary_phone === normPhone) : null;
  if (existing) return existing.id;

  const id = crypto.randomUUID();
  await db.put("people", { id, full_name: name, primary_phone: normPhone });
  return id;
}

export async function localSaveSubmission(record) {
  const db = await getDb();
  const id = record.id || crypto.randomUUID();
  const row = { ...record, id, created_at: record.created_at || new Date().toISOString() };
  await db.put("audio_submissions", row);
  return id;
}

export async function localListSubmissions() {
  const db = await getDb();
  const rows = await db.getAll("audio_submissions");
  return rows.sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
}
