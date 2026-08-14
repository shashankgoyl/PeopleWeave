# Task 4 — Data issues report

Source files (as given):
- `data/source1_naukri_applicants.csv` — 42 data rows. Full Name, Email, Phone, City,
  Experience (Years), Current CTC, Applied Date, Skills.
- `data/source2_gig_workers.csv` — 32 data rows. email_id, worker_name, rate, location,
  status, skill_tags. **No phone column at all.**
- `data/source3_cbnexus_contacts.csv` — 31 data rows. Name, Phone Number, City, Verified,
  Projects Completed. **No email column, no skills column at all.**

Numbers below come straight out of `pipeline/merged_preview.json` (produced by
`python pipeline/merge.py --dry-run`), not hand-counted, so they're reproducible.

## The core problem: no field is common to all 3 files

Source1 has both email and phone. Source2 has only email. Source3 has only
phone. So there is no column you can join all three files on directly —
source2 and source3 share **zero** overlapping fields with each other. The
only way to link a source2 record to a source3 record is transitively,
through a source1 record that shares an email with one and a phone with the
other (or, when no such bridge row exists, through name similarity — see below).
`pipeline/merge.py`'s docstring and the `PHASE 1 / PHASE 2` split walk through
exactly how this is handled.

## Issues found and what I did about them

### 1. Structural/row-level corruption (auto-detected, 3 rows dropped)
Run `python pipeline/merge.py --dry-run` and check `row_level_issues` in the
output — these are found programmatically, not by manual inspection:

- **`source2_gig_workers.csv`, line 12**: a completely blank row
  (`,,,,,`). Dropped — nothing to recover.
- **`source2_gig_workers.csv`, line 20**: a row whose columns are shifted —
  `skill_tags` ends up in the `email_id` position and everything else shifts
  one column over: `"react, javascript, mysql", ISHA.CHOPRA95@..., Isha
  Chopra, 1406/hr, Pune, active`. I detect this by checking whether the value
  in the email column actually looks like an email; if it doesn't but a
  *different* column in that row does, it's flagged as shifted rather than
  silently ingested as garbage. I chose **not** to auto-repair by guessing
  the rotation — that's a one-off heuristic that could misfire on a
  differently-shaped corruption elsewhere — and confirmed by hand that this
  exact person (Isha Chopra) already has a clean, correctly-formatted row
  earlier in the same file, so nothing is actually lost by dropping it.
- **`source3_cbnexus_contacts.csv`, line 16**: the header row
  (`Name,Phone Number,City,Verified,Projects Completed`) appears a *second
  time*, in the middle of the data. This is the classic signature of two CSV
  exports being pasted together without stripping the second header. Detected
  by checking if a row's values exactly equal the field names, and dropped.

### 2. Duplicate rows within a single source file
- `source1_naukri_applicants.csv` has "R. Verma" and "Rohit Verma" as two
  separate rows with the *same* email, phone, city, CTC, applied date, and
  skills — one person entered twice with an abbreviated name on one copy.
- Same file: "Nikhil Chopra" appears twice with the same phone/city/CTC/date/
  skills but two different emails (`nikhil.chopra70@example.com` and
  `alt.nikhil.chopra70@example.com` — the "alt." prefix is a giveaway).
Both collapse into one person automatically because the exact-phone match
in Phase 1 doesn't care that the name string or email differs. I did **not**
special-case "alt." emails to prefer the non-"alt." one as primary — the
pipeline just picks the alphabetically-first email, which for this pair
happens to pick `alt.nikhil.chopra70@...`. Cosmetically not ideal; documented
here rather than silently fixed, since I didn't want to hand-tune a rule
around a single example (see the Stuck Log for more on this trade-off).

### 3. Inconsistent formatting that would break naive matching
- **Phone numbers**: seen as `+919000000254`, `9000000237`, `09000000287`
  (leading 0), `+91-9000000131` (with a dash), `919000000231` (country code,
  no `+`). All normalized to the last 10 digits after stripping everything
  non-numeric and dropping a leading `91` country code or a leading trunk `0`.
- **Emails**: mixed case throughout source2 in particular
  (`ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG` vs `isha.chopra95@mailtest.example.org`)
  — without lower-casing before comparing, this alone would have produced
  duplicate people for at least 6 individuals. Normalized to lowercase +
  trimmed, and validated against a basic email-shape regex (catches typos
  like a missing `@` or TLD rather than trusting the column blindly).
- **City names**: `Gurgaon` / `Gurugram`, `Delhi` / `New Delhi` / `Delhi NCR`,
  `Bangalore` / `Bengaluru`, plus casing (`NOIDA`/`Noida`/`noida`) and stray
  trailing spaces (`"Noida "`, `"gurugram "`). Normalized through an alias
  table (`pipeline/clean.py::normalize_city`) onto one canonical spelling per
  city. City wasn't needed for identity matching, but it's stored per-source
  in `person_sources.raw_row`, so this matters if it's ever used for
  reporting/filtering later.
- **Dates** (`source1`'s "Applied Date"): at least 4 different formats mixed
  in the *same column* — `24-07-2026` (DD-MM-YYYY), `2026-08-08` (YYYY-MM-DD),
  `7 Jul 2026`, and `07/13/2026` (MM/DD/YYYY — unambiguous here because 13
  can't be a month, which is how I confirmed slash-dates are MM/DD and not
  DD/MM in this file). `pipeline/clean.py::normalize_date` parses all four
  into ISO `YYYY-MM-DD`; anything it can't parse is left alone and would show
  up as `None` if you inspect it, rather than being silently mis-parsed.

### 4. Ambiguous "is this actually the same person?" cases — flagged, not guessed
The merge script logs these to `merge_audit` as `fuzzy_name_needs_review`
instead of merging them, because guessing wrong here is worse than leaving a
human to decide:

- **"Arjun Mehta"**: exists as *two distinct clusters* in the final output.
  One is `naukri_applicants` + the first `cbnexus_contacts` entry (matched by
  phone `9000000131`, email `arjun.mehta9@example.in`). The other is
  `gig_workers` + the *second* `cbnexus_contacts` "Arjun Mehta" entry (email
  `arjun.mehta77@mailtest.example.org`, phone `9000000272`) — matched to each
  other only by name, since neither has a field that overlaps with the first
  cluster, but their identifiers actively **conflict** with cluster one's
  (different phone, different email), so they're kept separate. This is a
  common enough Indian name that two different real people sharing it is
  entirely plausible — I'd rather ship 2 correctly-separated "Arjun Mehta"
  records than 1 wrongly-merged one. See the Stuck Log for how this shaped
  the matching algorithm.
- **"Deepak Nair"**: two source2 rows, `deepak.nair44@example.com` and
  `deepak.nair57@example.in`. The first matches source1's Deepak Nair by
  email; the second doesn't match anything else in the dataset and is left
  as its own unresolved person, flagged for review rather than assumed to be
  the same Deepak Nair with a second email.

### 5. Clean cross-file bridges with no source1 record at all (the real test of "no common ID")
Five people — **Divya Chopra, Manish Bhatia, Karan Chopra, Vikram Mehta**, and
the second **Arjun Mehta** above — exist *only* in `gig_workers` (email) and
`cbnexus_contacts` (phone), with no `naukri_applicants` row to bridge them.
Since those two files share no column at all, the only way to link them is
name similarity, with no conflicting identifiers on either side. These are
exactly the cases that would be silently missed (left as duplicate people) by
a naive "join on email, join on phone" script, and exactly why a fuzzy-name
fallback pass is in the pipeline at all.

### 6. Unit/scale inconsistency (found, documented, not force-fixed)
- `source1`'s **Current CTC** column mixes what look like two different
  units: some values are large raw numbers (`417964`, `775670`) consistent
  with annual salary in rupees, others are small decimals (`4.2`, `8.3`,
  `5.1`) consistent with **lakhs per annum** (i.e. `4.2` meaning ₹4.2L =
  ₹420,000). I did not silently rescale these — the assignment's core schema
  is about identity + skills, not compensation, so CTC isn't written into
  `people` at all; it's preserved verbatim in `person_sources.raw_row` for
  whoever needs it, with this ambiguity flagged here rather than guessed at.
- `source2`'s **rate** column mixes hourly (`1415/hr`) and monthly
  (`15k/month`) pay, which aren't directly comparable without knowing
  assumed hours/month. Same treatment: preserved raw, not normalized, flagged
  here.
- `source2`'s **status** column has 3 real categories (`Active`, `Inactive`,
  `paused`) inconsistently cased (`ACTIVE`, `active`, `Active`) — this is a
  genuine 3-way category, not just a casing issue, so I didn't collapse
  `paused` into `Inactive`.

### 7. Missing / placeholder values
`clean.py::PLACEHOLDER_VALUES` treats things like `N/A`, `-`, `none`, blank
strings, and the literal `0000000000` phone as "no data", not "the value is
literally the string N/A" — otherwise every placeholder in the file would
have been (incorrectly) treated as a valid, matchable value, and multiple
unrelated people with blank emails would have been merged into one "N/A"
person by an accidental exact-string match.

## Summary numbers
| | |
|---|---|
| Raw data rows across all 3 files | 105 |
| Dropped as structurally corrupt (blank / shifted / embedded header) | 3 |
| Usable rows ingested | 102 |
| Unique people after merge | 55 |
| Duplicate rows collapsed | 47 |
| Ambiguous pairs flagged for human review (not auto-merged) | 3 |
