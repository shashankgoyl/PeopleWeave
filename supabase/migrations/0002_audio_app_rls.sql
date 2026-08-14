-- The audio app is now a pure client-side React app (no backend server, no
-- service_role key involved) - it talks to Supabase directly from the
-- browser using the *anon* key. That means Row Level Security has to be
-- turned on and explicitly opened up for exactly the tables/bucket this app
-- touches, or every request from the browser will simply be rejected.
--
-- This is intentionally permissive for a public "anyone can submit" intake
-- form with no login step (matches the assignment: gig workers submitting
-- audio, no auth flow specified). See docs/stretch_scaling.md for what to
-- tighten before a real production launch (e.g. restricting SELECT on
-- audio_submissions so the public listing doesn't expose every phone number,
-- adding an edge function instead of direct anon writes, rate limiting).

alter table people enable row level security;
alter table audio_submissions enable row level security;

drop policy if exists "anon can read people" on people;
create policy "anon can read people"
  on people for select
  to anon
  using (true);

drop policy if exists "anon can insert people" on people;
create policy "anon can insert people"
  on people for insert
  to anon
  with check (true);

drop policy if exists "anon can read audio_submissions" on audio_submissions;
create policy "anon can read audio_submissions"
  on audio_submissions for select
  to anon
  using (true);

drop policy if exists "anon can insert audio_submissions" on audio_submissions;
create policy "anon can insert audio_submissions"
  on audio_submissions for insert
  to anon
  with check (true);

-- Storage bucket for the raw audio files, uploaded directly from the browser.
insert into storage.buckets (id, name, public)
values ('audio-submissions', 'audio-submissions', true)
on conflict (id) do nothing;

drop policy if exists "public can read audio files" on storage.objects;
create policy "public can read audio files"
  on storage.objects for select
  using (bucket_id = 'audio-submissions');

drop policy if exists "anon can upload audio files" on storage.objects;
create policy "anon can upload audio files"
  on storage.objects for insert
  to anon
  with check (bucket_id = 'audio-submissions');
