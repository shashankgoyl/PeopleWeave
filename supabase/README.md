# Supabase setup

1. Create a free project at https://supabase.com/dashboard.
2. Get your project values from **Project Settings → API**:
   - `Project URL` → `SUPABASE_URL`
   - `service_role` secret key → `SUPABASE_SERVICE_KEY` (needed because the pipeline
     writes/upserts data — the anon key is read-only under RLS by default)
3. Run the schema in `migrations/0001_init.sql`, either:
   - **Dashboard**: SQL Editor → paste the file → Run, OR
   - **CLI**:
     ```bash
     npm install -g supabase
     supabase login
     supabase link --project-ref <your-project-ref>
     supabase db push
     ```
4. (Optional, for storing actual audio files in Supabase instead of local disk)
   Storage → Create bucket → name it `audio-submissions` → set to public (fine for
   a demo; for real use you'd sign URLs instead).

That's it — no RLS policies are added on purpose, since the pipeline and app talk
to Supabase with the **service_role** key server-side only. Never expose that key
to the browser.
