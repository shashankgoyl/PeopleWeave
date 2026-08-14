# Task 5 — Scaling the audio app to 5,000 gig workers in a weekend

(Written against the current architecture: static React app, no backend
server, writing directly to Supabase from the browser with the anon key.)

## What breaks first
1. **Trusting client-reported audio properties.** Duration/sample rate/
   loudness are computed in the browser and submitted as plain values in the
   insert — nothing stops a modified client from lying about them, or from
   submitting a 45-minute file while claiming it's 30 seconds. Fine for a
   trusted demo; not fine once real money/payment is tied to submission
   count or duration. This is the first thing I'd fix, not the last — an
   edge function that re-derives at least duration server-side (cheap to do
   from the uploaded file's own container metadata) closes this.
2. **Supabase free-tier limits, hit directly by 5,000 browsers.** No queue,
   no backend to absorb a burst — every submission is a direct
   insert+storage-upload from someone's phone. A single push notification
   telling 5,000 people "submit now" turns into a spike of concurrent direct
   writes against one Postgres instance and one storage bucket; free-tier
   connection/rate limits would be the first thing to throttle, not a
   server we control.
3. **The open anon RLS policies were sized for a demo, not 5,000 strangers.**
   `supabase/migrations/0002_audio_app_rls.sql` lets any anon key holder
   insert unlimited rows and read every submission (including phone
   numbers) — fine when "anon key holder" means "people who loaded the
   intake page," much less fine at scale where the same open policy makes
   it trivial to scrape every worker's phone number off `/submissions`, or
   script thousands of fake inserts.
4. **No de-dup / idempotency on submit.** A flaky mobile connection mid
   -upload, or someone double-tapping submit because the UI didn't clearly
   show it was working, creates a second full row + a second audio file.
   At 5,000 users on patchy connections this will happen constantly.
5. **Browser codec/API compatibility.** `AudioContext.decodeAudioData` and
   `MediaRecorder` are broadly supported but not universally consistent
   (older Android WebViews, some in-app browsers used by messaging apps)
   — a worker opening the link inside, say, a WhatsApp in-app browser is a
   very real scenario for this audience, and any gaps there show up as
   silent failures with no server log to check, only "it didn't work" from
   a user with no ability to describe why.

## What I'd change before launch, in priority order
- **Put a thin edge function (Supabase Edge Functions or similar) in front
  of writes**, instead of raw anon inserts — even a minimal one gives you a
  place to rate-limit per phone/IP, re-validate the uploaded file
  server-side, and stop scraping the submissions table wholesale.
- **Idempotency key per submission** — a client-generated UUID sent with the
  insert, so a retried request upserts instead of duplicating.
- **Tighten the RLS policies** — scope `SELECT` on `audio_submissions` (the
  public "all submissions" view shouldn't be truly public at 5,000-worker
  scale), and consider requiring a lightweight token (e.g. a magic link per
  worker) rather than a fully open anon-insert policy.
- **Client-side caps enforced before upload starts** — max recording
  duration, max file size — so a bad file never even reaches the upload
  step, cutting both bandwidth cost and the "did it actually work" ambiguity
  down.
- **Real user-facing upload status** (progress + clear success/failure
  state), specifically to reduce the double-submit problem from #4 — a lot
  of duplicate-submission problems at scale are a UX problem wearing a
  technical costume.
- **A visible failure state, not just a browser console error** — if
  `decodeAudioData` throws on a device/codec combo we didn't test, the
  worker needs to see "please try again / use a different browser," not a
  silently stuck submit button.

## Storage & cost, roughly
5,000 workers × (say) 2 clips × 1-2MB each ≈ 10-20GB for the weekend —
comfortably inside Supabase Storage's free/low tiers. The real cost risk
isn't the storage size, it's **uncapped duration** (someone's 20-minute
file) or **retries multiplying the row/file count** (#4 above) — both cheap
to guard against up front (max duration + max file size enforced
client-side, idempotency key) and expensive to discover after 5,000 people
have already used the app once.

## Duplicates (linking submissions to Task 1's `people`)
At this scale, the same de-dup logic from Task 1 (email/phone matching, with
name-only matches flagged for review rather than auto-merged) should run as
a **scheduled job against `audio_submissions` → `people`**, not just once at
ingestion — new workers show up across the whole weekend, not in one batch,
and the client-side `findOrCreatePerson` call only checks for an exact phone
match at submit time, not fuzzy duplicates.

## Failure visibility
Right now a failed analysis just shows a flash message to the one person who
hit it, with no record of it anywhere else. At 5,000 submissions I'd want
failed attempts to land somewhere queryable (even a `failed_submissions`
table logged from the client) so a systemic issue — a codec gap on one
common device, say — surfaces as "N failures in the last hour, all from the
same user agent" instead of being invisible until someone manually
complains.
