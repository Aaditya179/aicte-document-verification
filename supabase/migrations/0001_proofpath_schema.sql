-- ProofPath AI (SIH26261): schema
--
-- ProofPath shares its Supabase project with Nirikshan (SIH26262). Everything ProofPath owns lives in
-- the `proofpath` schema, so nothing here can clash with Nirikshan's tables, views or policies in
-- `public`. Sign-in accounts (auth.users) are shared by both apps: a ProofPath role comes only from
-- proofpath.members, never from the account's app_metadata, which holds the Nirikshan role.
--
-- Only the API's service role can read or write this schema. The browser never queries it directly,
-- so anon and authenticated get no grants, and RLS is on with no policies as a second lock.
--
-- After running this file: Project Settings -> Data API -> Exposed schemas, add `proofpath`.

create schema if not exists proofpath;

grant usage on schema proofpath to service_role;
alter default privileges in schema proofpath grant all on tables to service_role;
alter default privileges in schema proofpath grant all on sequences to service_role;
alter default privileges in schema proofpath grant execute on functions to service_role;

-- ---------------------------------------------------------------------------------------------
-- People and institutions
-- ---------------------------------------------------------------------------------------------

create table proofpath.institutions (
  id            uuid primary key default gen_random_uuid(),
  aicte_id      text unique,
  name          text not null,
  state         text,
  city          text,
  created_at    timestamptz not null default now()
);

-- A shared auth account becomes a ProofPath user only with a row here
create table proofpath.members (
  user_id         uuid primary key references auth.users (id) on delete cascade,
  role            text not null check (role in ('institution', 'verifier', 'analyst', 'auditor', 'admin')),
  institution_id  uuid references proofpath.institutions (id),
  full_name       text,
  created_at      timestamptz not null default now(),
  check (role <> 'institution' or institution_id is not null)
);

-- ---------------------------------------------------------------------------------------------
-- The case file: one per application, holding its documents and everything read from them
-- ---------------------------------------------------------------------------------------------

create table proofpath.cases (
  id                uuid primary key default gen_random_uuid(),
  case_no           text not null unique,
  institution_id    uuid not null references proofpath.institutions (id),
  application_type  text not null,
  academic_year     text not null,
  status            text not null default 'open' check (status in ('open', 'in_review', 'closed')),
  assigned_to       uuid references auth.users (id),
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

create table proofpath.documents (
  id            uuid primary key default gen_random_uuid(),
  case_id       uuid not null references proofpath.cases (id) on delete cascade,
  doc_type      text not null,               -- lease, building_plan, fire_noc, faculty_list, ...
  title         text not null,
  storage_path  text,                        -- object in the proofpath-documents bucket
  sha256        text,                        -- the same file in two cases is a cross-institution signal
  mime_type     text,
  size_bytes    bigint,
  page_count    int,
  uploaded_by   uuid references auth.users (id),
  uploaded_at   timestamptz not null default now()
);

-- A fact is one value read from one place in one document, with where it came from
create table proofpath.facts (
  id              uuid primary key default gen_random_uuid(),
  case_id         uuid not null references proofpath.cases (id) on delete cascade,
  document_id     uuid references proofpath.documents (id) on delete cascade,
  field           text not null,             -- institution_name, land_area, survey_no, valid_until, faculty_id, ...
  value_text      text not null,             -- exactly as printed
  value_norm      jsonb,                     -- parsed for comparison, e.g. {"sq_m": 40468.6}
  match_key       text,                      -- normalised identity used to find the same thing elsewhere
  page            int,
  source_quote    text,                      -- the line the value was read from
  confidence      numeric(4, 3) check (confidence between 0 and 1),
  extracted_by    text not null default 'ocr' check (extracted_by in ('ocr', 'llm', 'manual', 'registry')),
  created_at      timestamptz not null default now()
);

-- The verdict on one field of a case, and why
create table proofpath.checks (
  id            uuid primary key default gen_random_uuid(),
  case_id       uuid not null references proofpath.cases (id) on delete cascade,
  field         text not null,
  status        text not null check (status in ('verified', 'conflict', 'unverified')),
  reason        text not null,
  fact_ids      uuid[] not null default '{}',
  rule          text,                        -- which rule produced the verdict
  reviewed_by   uuid references auth.users (id),
  reviewed_at   timestamptz,
  review_note   text,
  created_at    timestamptz not null default now(),
  unique (case_id, field)
);

-- ---------------------------------------------------------------------------------------------
-- Patterns across institutions, which checking one application at a time cannot see
-- ---------------------------------------------------------------------------------------------

create table proofpath.patterns (
  id               uuid primary key default gen_random_uuid(),
  kind             text not null,            -- reused_document, shared_faculty, same_land_parcel, ...
  match_key        text not null,
  summary          text not null,
  severity         text not null default 'medium' check (severity in ('low', 'medium', 'high')),
  institution_ids  uuid[] not null default '{}',
  case_ids         uuid[] not null default '{}',
  fact_ids         uuid[] not null default '{}',
  status           text not null default 'open' check (status in ('open', 'confirmed', 'dismissed')),
  reviewed_by      uuid references auth.users (id),
  review_note      text,
  detected_at      timestamptz not null default now(),
  unique (kind, match_key)
);

-- ---------------------------------------------------------------------------------------------
-- Audit: SHA-256 hash chain, each entry hashing the previous hash plus its own payload
-- ---------------------------------------------------------------------------------------------

create table proofpath.audit_log (
  seq          bigserial primary key,
  at           timestamptz not null default now(),
  actor_id     uuid,
  actor_role   text,
  action       text not null,
  entity_type  text not null,
  entity_id    text,
  before       jsonb,
  after        jsonb,
  reason       text,
  prev_hash    text not null,
  hash         text not null unique
);

create or replace function proofpath.audit_block() returns trigger as $$
begin
  raise exception 'proofpath.audit_log is append-only';
end;
$$ language plpgsql;

create trigger audit_no_change before update or delete on proofpath.audit_log
  for each row execute function proofpath.audit_block();

create index on proofpath.cases (institution_id);
create index on proofpath.documents (case_id);
create index on proofpath.documents (sha256);
create index on proofpath.facts (case_id, field);
create index on proofpath.facts (field, match_key);
create index on proofpath.checks (case_id, status);
create index on proofpath.patterns (status);

-- Tables created above, before the default privileges applied to them
grant all on all tables in schema proofpath to service_role;
grant all on all sequences in schema proofpath to service_role;

alter table proofpath.institutions enable row level security;
alter table proofpath.members      enable row level security;
alter table proofpath.cases        enable row level security;
alter table proofpath.documents    enable row level security;
alter table proofpath.facts        enable row level security;
alter table proofpath.checks       enable row level security;
alter table proofpath.patterns     enable row level security;
alter table proofpath.audit_log    enable row level security;

-- Private bucket, separate from Nirikshan's `documents` bucket
insert into storage.buckets (id, name, public)
values ('proofpath-documents', 'proofpath-documents', false)
on conflict (id) do nothing;
