# Stuck log

**A note on how this was built, up front:** this project was built with heavy
AI assistance (Claude, in an agentic coding session) — the merge algorithm,
the schema, the Flask app, and the n8n export were all written and iterated
on with an AI doing the typing. Given that this assignment's own stuck-log prompt
explicitly asks "what you asked AI, what suggestions you rejected and why,"
that seems like expected/normal practice here, not something to hide. What
follows is a genuine account of the hardest technical calls made *during
that session* — real problems that came up while building this, and how
they got resolved. If you're submitting this as your own take-home, read
through this build with me (or re-run it and hit these same problems
yourself) before you turn it in — the whole point of this section is to show
your own judgment, and that only works if it's actually yours.

---

## 1. "No common ID across all 3 files" turned out to be worse than expected

The first pass at the merge logic did what most people would do first: union
records that share an exact email, union records that share an exact phone,
then fall back to fuzzy name matching for anything left over, merging
whenever two names were similar enough and didn't have *directly*
conflicting fields.

That worked fine on the first two files — until "Arjun Mehta" showed up.
There are two different real identities hiding behind that name across the
3 files: one pair of rows (from `naukri_applicants` + one `cbnexus_contacts`
row) sharing a phone number, and a completely separate pair (from
`gig_workers` + a *different* `cbnexus_contacts` row) sharing nothing with
the first pair at all — different email, different phone. Pairwise fuzzy
matching happily walked A→B (no conflict, B has no phone to conflict on) and
then B→C (no conflict, C has no email to conflict on), and the transitive
closure of a union-find data structure means A and C end up in the same
cluster even though A and C themselves have directly conflicting phone
numbers that would have blocked a merge if compared head-on.

**What I searched / asked the AI:** described the exact symptom — "record A
and record C have conflicting phones but ended up in the same cluster
because they're each connected to B" — and asked for options rather than a
fix, since this felt like a design problem, not a bug. The AI's fix was
cluster-aware conflict checking: before merging two clusters via a fuzzy
name match, check *every* member's email/phone across *both entire
clusters*, not just the two records whose names happened to match.

**What I rejected:** the first thing the AI suggested was tightening the
fuzzy match threshold (e.g. only auto-merge fuzzy names above 98% instead of
95%). I pushed back on that because it doesn't actually solve the problem —
"Arjun Mehta" vs "Arjun Mehta" is a 100% name match either way; the issue
isn't fuzziness in the *name comparison*, it's that the *conflict check* was
too narrow (pairwise instead of cluster-wide). A higher threshold would have
just made the pipeline miss more real matches without fixing the actual bug.
The cluster-wide conflict check was the right fix, and it's what's in
`pipeline/merge.py` now (see the `cluster_conflicts()` function and the
Phase 1 / Phase 2 split in the docstring).

## 2. Deciding whether to auto-repair the corrupted row in `gig_workers`

One row in `source2_gig_workers.csv` has its columns rotated —
`skill_tags` ends up where `email_id` should be, and everything shifts over
by one. It was tempting to write a generic "detect and un-rotate" fixer.

**What I searched:** mostly just re-read the actual bad row character by
character against the header to confirm it really was a clean rotation and
not something messier (it was — `[skill_tags, email_id, worker_name, rate,
location, status]` instead of `[email_id, worker_name, rate, location,
status, skill_tags]`).

**What I rejected and why:** writing a rotation-detector felt like
over-fitting to one example row in one file. A real production feed could
corrupt columns in all sorts of ways (a dropped column, a stray delimiter
inside an unescaped value, two columns swapped instead of rotated) — a
"fix this one specific shape of corruption" function gives false confidence
that corrupted rows are being "handled" when really only one exact pattern
is covered. Instead the pipeline does the safer thing: detect that the row
doesn't line up with its own header (email-shaped value found in the wrong
column), drop it, and log exactly why in `row_level_issues`. I confirmed by
hand that the same person already has a valid row elsewhere in the file, so
nothing was actually lost — but the code doesn't rely on knowing that ahead
of time, it just refuses to guess.

## 3. The noise-estimate heuristic gave a nonsense result on its first test

For the "noise/quality" bonus in Task 3, the plan was: split the clip into
short windows, take the gap between the loud windows and the quiet windows
as a rough SNR proxy. First test used a synthetic clean 440Hz tone plus a
tiny bit of noise vs. the same tone plus a lot of noise — and *both* came
back classified as `"noisy"`, including the clean one.

**What went wrong:** a continuous sine tone has almost no dynamic range —
every 50ms window is about equally loud, so the "quiet window" and "loud
window" percentiles end up nearly identical regardless of how much
background noise is mixed in, which the heuristic reads as "no headroom
between signal and noise floor" → noisy. It wasn't a bug in the code, it was
a bad test fixture — real speech has pauses between words (genuine silence,
not just quieter tone), which is what the heuristic actually needs to find a
noise floor to compare against.

**How this got resolved:** rebuilt the test audio to have an on/off envelope
(bursts of tone separated by real silence) to actually resemble speech, and
re-ran the same heuristic against a clean-background version and a
noisy-background version of that. That gave the expected split (`"clean"`
vs `"noisy"`) — see the two test cases in the build (search this
conversation for `test_clean_speech.wav` / `test_noisy_speech.wav`, or run
`node audio_app/src/lib/audioAnalysis.test.mjs` for the JS port of the same
test, added after the Flask→React migration below). Worth being upfront
about: this is a rough heuristic, not a validated audio quality metric — the
comment above `analyzeAudioBlob` in `audio_app/src/lib/audioAnalysis.js`
says as much rather than overselling what a few lines of percentile math
actually proves.

## 4. Dropping Flask entirely for the audio app

The original Task 3 was Flask + pydub (which shells out to ffmpeg) doing the
audio decoding server-side. When asked to move to React and drop Flask if it
could genuinely be dropped rather than kept around for its own sake, the
real question was: does audio *analysis* need a server at all?

**What I checked:** whether the browser's own `AudioContext.decodeAudioData`
exposes enough to replace what pydub was doing — it does. `AudioBuffer` gives
you `.duration` and `.sampleRate` directly off the decode, and you already
have the file's byte size client-side for the bitrate estimate, so the RMS
loudness and windowed-SNR noise heuristic are just arithmetic over
`getChannelData()` — no different from what the Python version was doing
over a NumPy-ish array, just in JS.

**What that meant for storage:** with no backend, something still has to
enforce who can write what to Supabase. The service_role key from the Flask
version can never go into browser JS (it bypasses every permission check),
so the swap meant switching to the anon key **and** actually turning on Row
Level Security with explicit policies (`supabase/migrations/0002_audio_app_rls.sql`)
— previously RLS was left off on purpose since only a trusted server touched
the DB. That's a real trade-off, not a free win: an open-anon-insert policy
is right for a public no-login submission form, but it also means anyone
with the anon key can read every row in `audio_submissions`, including phone
numbers. Documented in `docs/stretch_scaling.md` rather than solved here,
since fixing it properly (e.g. an edge function, or scoping SELECT somehow)
is more than this assignment's scope needs.

**What I rejected:** keeping a thin Flask/Node API purely as a proxy to
Supabase (so the service_role key stays server-side) was the "safer" middle
ground, and I considered it. Went with the fully client-only version instead
because the person specifically asked whether Flask could be replaced
outright "if that works fine" — and for this assignment's threat model
(a demo take-home, not a real production intake system with sensitive data),
it does. That trade-off is written down here and in the RLS migration's
comments rather than silently made.
