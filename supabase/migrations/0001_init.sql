-- PeopleWeave: unified people database
-- Run this via `supabase db push`, or paste into the Supabase SQL editor.

create extension if not exists "pgcrypto";

-- One row per real human, regardless of how many source systems mention them.
create table if not exists people (
    id                 uuid primary key default gen_random_uuid(),
    full_name          text not null,
    normalized_name    text generated always as (
                           lower(regexp_replace(trim(full_name), '\s+', ' ', 'g'))
                       ) stored,
    primary_email      text,
    primary_phone      text,           -- normalized to last-10-digits, India-first
    skill_category     text,           -- filled in by the n8n + Groq automation (Task 2)
    skill_confidence   numeric,
    source_systems     text[] not null default '{}',
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now()
);

create index if not exists idx_people_email on people (primary_email);
create index if not exists idx_people_phone on people (primary_phone);
create index if not exists idx_people_norm_name on people (normalized_name);

-- Every email a person has used across any source system.
create table if not exists person_emails (
    id          uuid primary key default gen_random_uuid(),
    person_id   uuid not null references people(id) on delete cascade,
    email       text not null,
    is_primary  boolean not null default false,
    unique(person_id, email)
);

-- Every phone number a person has used across any source system.
create table if not exists person_phones (
    id          uuid primary key default gen_random_uuid(),
    person_id   uuid not null references people(id) on delete cascade,
    phone       text not null,          -- normalized digits
    raw_phone   text,                   -- original as seen in the source file
    is_primary  boolean not null default false,
    unique(person_id, phone)
);

-- Raw lineage: exactly what each source system said about this person,
-- kept verbatim (as jsonb) so nothing from the original CSVs is ever lost.
create table if not exists person_sources (
    id                uuid primary key default gen_random_uuid(),
    person_id         uuid not null references people(id) on delete cascade,
    source_system     text not null,     -- 'recruitment_gigs' | 'cbnexus' | 'internal_automations'
    source_record_id  text,              -- their id/user_id/emp_code
    raw_skills_text   text,              -- free-text skills/tools field, used for Task 2 tagging
    raw_row           jsonb not null,
    ingested_at       timestamptz not null default now()
);

create index if not exists idx_sources_person on person_sources (person_id);

-- Audit trail of merge decisions, so every "these are the same person" call is explainable.
create table if not exists merge_audit (
    id            uuid primary key default gen_random_uuid(),
    person_id     uuid references people(id) on delete set null,
    matched_on    text not null,      -- 'email' | 'phone' | 'fuzzy_name (needs review)'
    confidence    numeric not null,   -- 1.0 for exact key match, 0-1 similarity score for fuzzy
    detail        text,
    created_at    timestamptz not null default now()
);

-- Task 3: audio submissions from the mini gig-worker app.
create table if not exists audio_submissions (
    id               uuid primary key default gen_random_uuid(),
    person_id        uuid references people(id) on delete set null,
    submitted_name   text not null,
    submitted_phone  text not null,
    file_path        text not null,      -- local path or Supabase Storage path/URL
    original_filename text,
    duration_seconds numeric,
    sample_rate_hz   integer,
    bitrate_kbps     numeric,
    loudness_db      numeric,            -- integrated loudness (approx. RMS dBFS)
    noise_estimate   text,               -- 'clean' | 'moderate_noise' | 'noisy' (bonus, rough heuristic)
    status           text not null default 'received',  -- received | processed | failed
    created_at       timestamptz not null default now()
);

create index if not exists idx_audio_person on audio_submissions (person_id);

-- Keep updated_at fresh on people
create or replace function set_updated_at() returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_people_updated on people;
create trigger trg_people_updated before update on people
for each row execute function set_updated_at();
