# Supabase setup

1. Create a free project at https://supabase.com/dashboard.
2. Get your project values from **Project Settings → API**:
   - `Project URL` → used as both `SUPABASE_URL` (pipeline) and
     `VITE_SUPABASE_URL` (audio app)
   - `service_role` secret key → `SUPABASE_SERVICE_KEY`, used **only** by the
     server-side merge pipeline in `pipeline/` (never ship this to a browser)
   - `anon` `public` key → `VITE_SUPABASE_ANON_KEY`, used by the React audio
     app, which talks to Supabase directly from the browser
3. Run both migrations, in order, either via the Dashboard SQL Editor (paste
   each file, Run) or the CLI:
   ```bash
   npm install -g supabase
   supabase login
   supabase link --project-ref <your-project-ref>
   supabase db push
   ```
   - `migrations/0001_init.sql` — core schema (Task 1)
   - `migrations/0002_audio_app_rls.sql` — Row Level Security + the
     `audio-submissions` storage bucket, needed because the audio app has no
     backend and talks to Supabase straight from the browser with the anon
     key. This migration also creates the storage bucket itself (via
     `insert into storage.buckets ...`) — no separate dashboard step needed.

That's it. The merge pipeline (`pipeline/`) uses the service_role key
server-side and is unaffected by RLS. The audio app (`audio_app/`) uses only
the anon key and depends on the policies in `0002_audio_app_rls.sql` to work
at all — without them, every insert/select from the browser gets rejected.
