import { supabase, USE_SUPABASE, AUDIO_BUCKET } from "./supabaseClient";
import { localFindOrCreatePerson, localSaveSubmission, localListSubmissions } from "./localDb";

function normalizePhone10(phone) {
  const digits = String(phone).replace(/\D/g, "");
  const stripped = digits.length > 10 && digits.startsWith("91") ? digits.slice(2) : digits;
  return stripped.length >= 10 ? stripped.slice(-10) : stripped || null;
}

/** Best-effort link to Task 1's `people` table by phone. Returns a person_id. */
export async function findOrCreatePerson(name, phone) {
  if (!USE_SUPABASE) return localFindOrCreatePerson(name, phone);

  const normPhone = normalizePhone10(phone);
  if (normPhone) {
    const { data: existing } = await supabase
      .from("people")
      .select("id")
      .eq("primary_phone", normPhone)
      .limit(1);
    if (existing && existing.length) return existing[0].id;
  }

  const { data, error } = await supabase
    .from("people")
    .insert({ full_name: name, primary_phone: normPhone, source_systems: ["audio_app"] })
    .select("id")
    .single();
  if (error) throw error;
  return data.id;
}

/**
 * Uploads the audio blob + inserts the audio_submissions row (Supabase mode),
 * or stores both in IndexedDB (local mode). `props` is the output of
 * analyzeAudioBlob(). Returns the created submission id.
 */
export async function saveSubmission({ name, phone, blob, filename, props, personId }) {
  if (!USE_SUPABASE) {
    return localSaveSubmission({
      person_id: personId,
      submitted_name: name,
      submitted_phone: phone,
      original_filename: filename,
      audio_blob: blob, // kept locally only - never sent anywhere in local mode
      status: "processed",
      ...props,
    });
  }

  const id = crypto.randomUUID();
  const ext = (filename && filename.split(".").pop()) || "webm";
  const path = `${id}.${ext}`;

  const { error: uploadError } = await supabase.storage
    .from(AUDIO_BUCKET)
    .upload(path, blob, { contentType: blob.type || "audio/webm", upsert: false });
  if (uploadError) throw uploadError;

  const { data: pub } = supabase.storage.from(AUDIO_BUCKET).getPublicUrl(path);

  const { error: insertError } = await supabase.from("audio_submissions").insert({
    id,
    person_id: personId,
    submitted_name: name,
    submitted_phone: phone,
    file_path: pub.publicUrl,
    original_filename: filename,
    status: "processed",
    ...props,
  });
  if (insertError) throw insertError;

  return id;
}

/** Returns rows newest-first, each with a `playback_url` ready for an <audio> tag. */
export async function listSubmissions() {
  if (!USE_SUPABASE) {
    const rows = await localListSubmissions();
    return rows.map((r) => ({
      ...r,
      playback_url: r.audio_blob ? URL.createObjectURL(r.audio_blob) : null,
    }));
  }

  const { data, error } = await supabase
    .from("audio_submissions")
    .select("*")
    .order("created_at", { ascending: false });
  if (error) throw error;
  return data.map((r) => ({ ...r, playback_url: r.file_path }));
}

export { USE_SUPABASE };
