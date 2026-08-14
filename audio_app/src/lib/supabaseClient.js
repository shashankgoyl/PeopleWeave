import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const USE_SUPABASE = Boolean(url && anonKey);

// Deliberately the anon key, not the service role key - this is a purely
// client-side app now (no backend), so only the anon key is safe to ship to
// the browser. See supabase/migrations/0002_audio_app_rls.sql for the RLS
// policies that make anon inserts/selects work for just the tables/bucket
// this app touches.
export const supabase = USE_SUPABASE ? createClient(url, anonKey) : null;

export const AUDIO_BUCKET = "audio-submissions";
