# Task 5 — Scaling the audio app to 5,000 gig workers in a weekend

## What breaks first
1. **The dev server and single SQLite file.** `flask run` / `app.run(debug=True)`
   is single-process and single-threaded by default — it will queue requests
   under any real concurrency, and SQLite write-locks the whole file per
   write, so concurrent submissions will start timing out or erroring well
   before 5,000 users, probably within the first few hundred concurrent
   uploads on launch morning.
2. **Local disk for audio files.** Free tiers (Render/Railway free dynos,
   etc.) have ephemeral or capped disk. A weekend of 5,000 people uploading
   even 30-second clips (~500KB-2MB each) is multiple GB, and a redeploy or
   restart on an ephemeral filesystem would just delete everything already
   collected.
3. **ffmpeg/pydub analysis blocking the request thread.** Right now, analysis
   happens synchronously inside the request that saves the file — for a slow
   or huge upload, that ties up a worker for the whole decode+analyze time.
   Under load this is the first thing that turns "slow" into "user sees a
   timeout and hits submit again."
4. **No de-dup / idempotency on submit.** Nothing stops the same worker from
   submitting the same recording 3 times because the page felt like it hung
   (see #3) and they hit submit again. At 5,000 users this will happen a lot.
5. **No queue/backpressure** — if 500 people all hit "submit" in the same
   minute (very plausible for a gig-work weekend push notification), the app
   has no way to shed load gracefully; it just falls over.

## What I'd change before launch, in priority order
- **Swap SQLite for real Postgres (Supabase already gives this)** and put the
  Flask app behind a production WSGI server (gunicorn, multiple workers) —
  this alone fixes most of the concurrency problem.
- **Upload straight to object storage, not local disk** — Supabase Storage
  (or S3) via a signed upload URL from the browser, so the app server never
  touches the raw bytes and disk limits stop mattering.
- **Move audio analysis off the request path** — save the file, insert a
  `status='received'` row immediately, return success to the user right
  away, and do duration/sample-rate/bitrate/loudness extraction in a
  background worker/queue (even a simple cron-polled "process pending rows"
  job would be a huge improvement over doing it inline).
- **Idempotency key per submission** — a client-generated UUID sent with the
  form, so a duplicate POST (retry, double-tap, flaky network) upserts
  instead of creating a second row.
- **Basic rate limiting per phone number/IP** — stop one confused or
  malicious user from submitting hundreds of times in a loop.
- **Client-side compression/format constraints** before upload (cap
  duration, encode to a smaller bitrate) so average file size and bandwidth
  cost don't balloon — 5,000 uncapped recordings could otherwise cost far
  more in storage/egress than expected.

## Storage & cost, roughly
5,000 workers × (say) 2 clips × 1-2MB each ≈ 10-20GB for the weekend. That's
comfortably inside any free/cheap object storage tier (Supabase Storage,
S3) — the real cost risk isn't storage size, it's **uncapped duration**
(someone uploads a 20-minute file) or **retries multiplying the count**
(#4 above), both of which are cheap to guard against up front (max duration
+ max file size enforced client- and server-side, idempotency key) but
expensive to discover after 5,000 people have already used the app.

## Duplicates
At this scale, the same de-dup logic from Task 1 (email/phone matching, with
name-only matches flagged for review rather than auto-merged) should run as
a **scheduled job against `audio_submissions` → `people`**, not just once at
ingestion — new workers show up over the whole weekend, not in one batch.

## Failure visibility
Right now a failed audio analysis is just logged and flashed to the one user
who hit it. At 5,000 submissions I'd want a `status='failed'` row to be
genuinely queryable (a small admin view: "N failed this hour, here's why")
rather than only visible in server logs — otherwise a systemic issue (e.g. a
codec ffmpeg can't decode) silently eats a chunk of submissions before
anyone notices.
