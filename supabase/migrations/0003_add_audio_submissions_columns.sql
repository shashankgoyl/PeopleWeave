-- The client-side audio analysis (src/lib/audioAnalysis.js) computes and
-- sends `channels` and `file_size_bytes` for every submission, but the
-- original 0001_init.sql table definition never included them, causing
-- PostgREST inserts to fail with "Could not find the 'channels' column of
-- 'audio_submissions' in the schema cache".
--
-- Applied directly to the live project via the Supabase MCP tool on
-- 2026-08-14; this file just keeps the migration history in source control
-- in sync with the database.

alter table audio_submissions
  add column if not exists channels integer,
  add column if not exists file_size_bytes bigint;
