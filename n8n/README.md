# Task 2 — n8n automation: Groq LLM skill-category auto-tagging

**What it does:** for every person in Supabase whose `skill_category` is still
`NULL`, it pulls their combined raw skills/tools text (from `person_sources`,
gathered across all 3 original systems), sends it to a Groq-hosted LLM with a
strict "respond with only this JSON shape" prompt, and PATCHes the result
(`skill_category`, `skill_confidence`) back onto their `people` row.

Categories used: `automation-heavy`, `web dev`, `data`, `sales-and-outreach`,
`content-and-design`, `ops-and-admin`, `other`.

## Why this flow (vs. the duplicate-alert option)

Task 1 already builds deterministic de-duplication with a full audit trail —
building a *second*, weaker version of the same idea in n8n felt redundant.
The skill-tagging flow instead adds something the merge pipeline can't do on
its own: turning messy free-text ("n8n, Zapier, chatbot dev" vs "Make.com,
webhook debugging" vs "automation scripts") into one consistent category per
person, which is exactly the kind of thing GrowBro-style CRMs need for lead
routing.

## Run it

1. Install n8n (pick one):
   ```bash
   npx n8n          # local, fastest for a demo
   # or: docker run -it --rm -p 5678:5678 n8nio/n8n
   ```
   Open http://localhost:5678
2. **Workflow → Import from File** → select `skill_tagging_workflow.json`.
3. Add environment variables n8n can read (Settings → Variables, or export
   before `npx n8n` on the CLI):
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
   - `GROQ_API_KEY` (free key from https://console.groq.com/keys)
4. Click the **Manual Trigger** node → "Execute workflow" to run it once
   on-demand (for the demo video). The **Every 6 hours** schedule trigger is
   there so it also runs unattended in production — leave it inactive for
   the video, since a manual run is what you want to show.
5. Check Supabase → `people` table → `skill_category` column should now be
   filled in for previously-untagged rows.

## Nodes, in order
`Trigger → Fetch untagged people (Supabase REST) → Fetch their raw skills
text (Supabase REST) → Combine into one string (Code) → Classify (Groq chat
completions) → Parse JSON response (Code) → Write skill_category back
(Supabase REST PATCH)`

Every Supabase call is a plain `httpRequest` node against the PostgREST API
(`{SUPABASE_URL}/rest/v1/...`) with the service key in the `apikey` /
`Authorization` headers — no special n8n Supabase-node credential setup
needed, which makes the exported JSON portable to any n8n instance.
