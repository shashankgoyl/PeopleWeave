# Task 3 — audio intake app (React, no backend)

A pure client-side React app (Vite). No Flask, no Node server, no ffmpeg —
audio decoding and property extraction happen in the browser via the Web
Audio API, and the app talks to Supabase directly using the anon key.

## Run it

```bash
npm install
cp .env.example .env      # fill in VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY,
                           # or leave them blank to use the local IndexedDB fallback
npm run dev
```

Open http://localhost:5050. Record in-browser or upload a file, submit, then
check `/submissions` — properties + a play button for every clip.

No Supabase account needed to try it locally: with `.env` empty/absent, the
app automatically stores everything in the browser's IndexedDB instead
(`src/lib/localDb.js`) — you'll see a "Local (browser only)" badge in the
header confirming which mode is active.

## Build for deployment

```bash
npm run build       # outputs static files to dist/
npm run preview     # serve the production build locally to sanity-check it
```

`dist/` is plain static HTML/JS/CSS — deploy it anywhere that serves static
files: Vercel, Netlify, Render (as a static site), GitHub Pages, or just
`ngrok http` a local `npm run preview` for the demo video. Set
`VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` as environment variables on
whichever platform you deploy to (Vite bakes them in at build time).

## How the pieces work
- **`src/lib/audioAnalysis.js`** — decodes the clip with
  `AudioContext.decodeAudioData` (native browser codecs, same ones used for
  `<audio>` playback) to get duration and sample rate directly off the
  decoded buffer; bitrate is derived from file size ÷ duration; loudness is
  RMS dBFS over the decoded PCM; the noise estimate is the same
  windowed-percentile heuristic as the original Python version. Run
  `node src/lib/audioAnalysis.test.mjs` to sanity-check the math without a
  browser.
- **`src/lib/storage.js`** — the only file that knows whether it's talking to
  Supabase or the local IndexedDB fallback; everything else (the pages,
  `findOrCreatePerson`, `saveSubmission`, `listSubmissions`) doesn't care
  which backend it's hitting.
- **`supabase/migrations/0002_audio_app_rls.sql`** — since this app has no
  server and uses the anon key straight from the browser, this migration
  turns on Row Level Security and opens up exactly the tables/bucket the app
  needs (nothing else). Intentionally permissive for a public no-login
  submission flow — see `docs/stretch_scaling.md` for what to lock down
  before a real 5,000-person launch.

## Why this replaced the Flask version
The original Task 3 used Flask + pydub/ffmpeg server-side. Once the person
asked to drop Flask in favor of React, the question was whether audio
analysis *needs* a server at all — and it doesn't: `decodeAudioData` gives
you duration/sample rate straight from the browser's own codec, and
Supabase's REST/Storage APIs are reachable directly from client-side JS with
RLS scoping what an anonymous browser is allowed to touch. That meant the
whole Python/Flask layer could come out rather than being kept around just
to shuttle bytes to Supabase.
