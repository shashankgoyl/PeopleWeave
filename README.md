# PeopleWeave

Merges 3 messy, overlapping data sources (a recruitment feed, a gig-worker
platform, and a CRM export — none of them sharing a common ID) into one
clean people database, with an LLM-powered skill-tagging automation on top
and a small audio-intake app that writes back into the same database.

Originally built as a take-home assignment; kept here as a working sample of
identity-resolution + automation + full-stack work. Built with heavy AI
assistance (see `docs/STUCK_LOG.md` for specifics on where and how).
Everything below is meant to be actually runnable, not just described.

## What's in here

```
data/                          the 3 real source CSVs
supabase/migrations/0001_init.sql   schema (Task 1)
supabase/migrations/0002_audio_app_rls.sql   RLS + storage bucket for the React audio app
pipeline/merge.py              ingests all 3 CSVs, dedupes people (Task 1)
n8n/skill_tagging_workflow.json     Groq-powered auto-tagging flow (Task 2)
audio_app/                     React (Vite) app: record/upload -> analyze in-browser -> store (Task 3)
docs/data_issues_report.md     Task 4
docs/stretch_scaling.md        Task 5
docs/STUCK_LOG.md              the hardest problems + how they got solved
```

## 1. Set up Supabase

Follow `supabase/README.md` — create a project, run the migration, grab your
`SUPABASE_URL` and `service_role` key.

## 2. Run the merge pipeline (Task 1)

```bash
cd pipeline
pip install -r requirements.txt
cp ../.env.example .env        # fill in SUPABASE_URL / SUPABASE_SERVICE_KEY
python merge.py --dry-run      # sanity check: builds merged_preview.json, no DB writes
python merge.py                # actually upserts into Supabase
```

`--dry-run` is worth running first — it prints a summary (raw rows read,
unique people resolved, duplicates collapsed, anything flagged for manual
review) and writes the full result to `pipeline/merged_preview.json` so you
can inspect exactly what got merged with what, and why, before it touches
your database. Against the 3 files in `data/`, this currently resolves
**105 raw rows → 55 unique people** (3 rows dropped as structurally corrupt,
47 duplicate rows collapsed, 3 ambiguous pairs flagged for human review
instead of guessed). Full breakdown in `docs/data_issues_report.md`.

## 3. Import the n8n automation (Task 2)

Get a free Groq API key at https://console.groq.com/keys, then follow
`n8n/README.md` — import `n8n/skill_tagging_workflow.json`, set 3 env vars
(`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `GROQ_API_KEY`), click the manual
trigger.

## 4. Run the audio app (Task 3)

Pure React (Vite), no backend server — see `audio_app/README.md` for the
full picture.

```bash
cd audio_app
npm install
npm run dev
```

Open http://localhost:5050. No Supabase setup required to try it locally —
if `VITE_SUPABASE_URL`/`VITE_SUPABASE_ANON_KEY` aren't set in `audio_app/.env`,
it falls back to browser IndexedDB automatically, so `npm run dev` just
works. Set those two (Project Settings → API → anon/public key, **not** the
service role key) to have it write into the real Supabase
`audio_submissions`/`people` tables instead — you'll also need to run
`supabase/migrations/0002_audio_app_rls.sql`, which opens up Row Level
Security for exactly what this client-only app needs to touch.

Record in-browser or upload a file → submit → see it appear at
`/submissions` with duration, sample rate, bitrate, loudness, and a rough
noise estimate (all computed client-side via the Web Audio API — no ffmpeg),
plus a play button.

## Deploying the audio app for the video (pick one)
- **ngrok** (fastest): `npm run build && npm run preview -- --host`, then
  `ngrok http 5050` in another terminal.
- **Vercel / Netlify / Render (static site)**: connect the repo, set the
  project root to `audio_app`, build command `npm run build`, output
  directory `dist`, and add `VITE_SUPABASE_URL`/`VITE_SUPABASE_ANON_KEY` as
  environment variables (Vite bakes them in at build time, so they need to
  be set *before* the build runs, not just at request time).

## Design decisions worth knowing about
- **Matching strategy**: exact email/phone = auto-merge (confidence 1.0).
  Fuzzy name match ≥95, checked against *every* member of both entire
  clusters for conflicts (not just the two matching records) = auto-merge.
  90-94, or any conflict found = logged for human review, never guessed.
  Full reasoning + the specific case that forced the cluster-wide conflict
  check (`"Arjun Mehta"`) is in `docs/STUCK_LOG.md` and
  `docs/data_issues_report.md`.
- **Audio storage/DB**: `audio_app/src/lib/storage.js` uses Supabase (anon
  key + RLS) if configured, otherwise a local IndexedDB fallback — so the
  grader can run it with zero cloud setup, and it's a 2-line env var change
  to point it at the real `people`/`audio_submissions` schema from Task 1.
- **No backend for Task 3**: audio decoding/analysis happens client-side via
  the Web Audio API (`AudioContext.decodeAudioData`), which is why Flask and
  ffmpeg could come out entirely — see `audio_app/README.md` for the "why"
  and `docs/STUCK_LOG.md` for how the swap went.
- **n8n flow chosen**: LLM skill-tagging over duplicate-alert, since Task 1
  already builds real de-duplication with an audit trail — see
  `n8n/README.md` for the reasoning.

## Task 4 & 5
See `docs/data_issues_report.md` and `docs/stretch_scaling.md`.

## Stuck log
See `docs/STUCK_LOG.md` — please read the note at the top of it before
reusing it as-is.
