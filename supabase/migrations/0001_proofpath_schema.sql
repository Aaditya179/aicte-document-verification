-- ProofPath AI (SIH26261): schema. Build spec section 5, adapted as recorded in CLAUDE.md, Part 2.
--
-- ProofPath shares its Supabase project with Nirikshan (SIH26262). Everything ProofPath owns lives in
-- the `proofpath` schema instead of `pp_`-prefixed tables in `public`, so nothing here can clash with
-- Nirikshan's tables, views, functions or policies. Sign-in accounts (auth.users) are shared: a
-- ProofPath role comes only from proofpath.members, never from the account's app_metadata.
--
-- Run order: 0001 (this file), 0002_rls.sql, 0003_seed_reference.sql.
-- Afterwards: Project Settings -> Data API -> Exposed schemas, add `proofpath`.

-- An earlier draft of this file (tables `cases`, `facts`, `checks`, `patterns`) was never applied.
-- If it was, stop rather than mix the two models; drop that schema by hand first.
do $$
begin
  if to_regclass('proofpath.cases') is not null then
    raise exception 'proofpath has the earlier draft schema (proofpath.cases). Drop schema proofpath cascade by hand, then rerun.';
  end if;
end $$;

create extension if not exists pgcrypto with schema extensions;

create schema if not exists proofpath;

grant usage on schema proofpath to service_role;
alter default privileges in schema proofpath grant all on tables to service_role;
alter default privileges in schema proofpath grant all on sequences to service_role;
alter default privileges in schema proofpath grant execute on functions to service_role;
-- Functions are executable by PUBLIC unless revoked; only the API may call ours
alter default privileges in schema proofpath revoke execute on functions from public;

-- ---------------------------------------------------------------------------------------------
-- People and institutions
-- ---------------------------------------------------------------------------------------------

create table proofpath.institutions (
  id            uuid primary key default gen_random_uuid(),
  code          text unique not null,
  name          text not null,
  city          text,
  is_fictional  boolean not null default true,
  created_at    timestamptz not null default now()
);

-- A shared auth account becomes a ProofPath user only with a row here (spec: pp_profiles)
create table proofpath.members (
  user_id         uuid primary key references auth.users (id) on delete cascade,
  full_name       text not null,
  role            text not null check (role in ('institution', 'reviewer', 'rule_admin')),
  institution_id  uuid references proofpath.institutions (id),
  created_at      timestamptz not null default now(),
  check ((role = 'institution') = (institution_id is not null))
);

-- ---------------------------------------------------------------------------------------------
-- Reference data (seeded by 0003)
-- ---------------------------------------------------------------------------------------------

create table proofpath.categories (code text primary key, label text not null);

create table proofpath.document_types (
  code                text primary key,
  label               text not null,
  has_expiry          boolean not null default false,
  signature_required  boolean not null default false,
  is_photo            boolean not null default false
);

create table proofpath.required_documents (
  id         uuid primary key default gen_random_uuid(),
  category   text not null references proofpath.categories (code),
  doc_type   text not null references proofpath.document_types (code),
  mandatory  boolean not null default true,
  unique (category, doc_type)
);

create table proofpath.extraction_templates (
  id           uuid primary key default gen_random_uuid(),
  doc_type     text not null references proofpath.document_types (code),
  field_name   text not null,
  value_type   text not null check (value_type in ('text', 'date', 'int', 'number')),
  regex        text not null,
  group_index  int not null default 1,
  required     boolean not null default false,
  unique (doc_type, field_name)
);

-- ---------------------------------------------------------------------------------------------
-- Applications and their documents
-- ---------------------------------------------------------------------------------------------

create table proofpath.applications (
  id                       uuid primary key default gen_random_uuid(),
  code                     text unique not null,
  institution_id           uuid not null references proofpath.institutions (id),
  category                 text not null references proofpath.categories (code),
  academic_year            text not null,
  workflow_status          text not null default 'draft'
                             check (workflow_status in ('draft', 'submitted', 'under_review', 'awaiting_institution', 'review_complete')),
  -- The administrative decision belongs to an authorised AICTE official. Nothing in ProofPath sets it.
  admin_status             text not null default 'pending' check (admin_status = 'pending'),
  declared_total_area_sqm  numeric,
  submitted_at             timestamptz,
  review_deadline          date,
  created_by               uuid references proofpath.members (user_id),
  created_at               timestamptz not null default now()
);

create table proofpath.documents (
  id                 uuid primary key default gen_random_uuid(),
  application_id     uuid not null references proofpath.applications (id) on delete cascade,
  doc_type           text not null references proofpath.document_types (code),
  version            int not null default 1,
  supersedes_id      uuid references proofpath.documents (id),
  status             text not null default 'current' check (status in ('current', 'superseded')),
  storage_path       text,
  original_name      text,
  mime               text,
  size_bytes         bigint,
  page_count         int,
  sha256             text,
  integrity_status   text not null default 'pending' check (integrity_status in ('pending', 'passed', 'failed')),
  integrity_note     text,
  processing_status  text not null default 'pending' check (processing_status in ('pending', 'processing', 'done', 'error')),
  processing_note    text,
  uploaded_by        uuid references proofpath.members (user_id),
  uploaded_at        timestamptz not null default now()
);

create table proofpath.extracted_fields (
  id              uuid primary key default gen_random_uuid(),
  document_id     uuid not null references proofpath.documents (id) on delete cascade,
  field_name      text not null,
  field_value     text,              -- normalised value used by the checks
  original_value  text,              -- exactly as read from the document, kept when a reviewer corrects it
  value_type      text,
  page_number     int,
  bbox            jsonb,
  source_method   text check (source_method in ('PDF_TEXT', 'OCR', 'MANUAL')),
  confidence      numeric,           -- OCR word confidence 0 to 1; null for PDF text
  review_state    text not null default 'auto' check (review_state in ('auto', 'needs_confirmation', 'confirmed', 'corrected')),
  review_reason   text,              -- why a value needs confirmation: not found, low confidence, ambiguous date
  reviewed_by     uuid references proofpath.members (user_id),
  reviewed_at     timestamptz
);

create table proofpath.faculty (
  id              uuid primary key default gen_random_uuid(),
  faculty_code    text,
  institution_id  uuid references proofpath.institutions (id),
  application_id  uuid references proofpath.applications (id) on delete cascade,
  document_id     uuid references proofpath.documents (id) on delete cascade,
  page_number     int,
  name_raw        text,
  name_norm       text,
  designation     text,
  qualification   text,
  masked_id       text,
  period_start    date,
  period_end      date
);

create table proofpath.media_assets (
  id           uuid primary key default gen_random_uuid(),
  document_id  uuid unique references proofpath.documents (id) on delete cascade,
  category     text check (category in ('lab', 'classroom', 'library', 'floor_plan', 'other')),
  phash        text,                 -- 16 hex characters = 64 bits
  width        int,
  height       int,
  exif         jsonb,
  taken_at     timestamptz,
  gps          jsonb
);

create table proofpath.rooms (
  id                      uuid primary key default gen_random_uuid(),
  application_id          uuid references proofpath.applications (id) on delete cascade,
  floor_plan_document_id  uuid references proofpath.documents (id),
  room_label              text,
  length_m                numeric,
  width_m                 numeric,
  area_sqm                numeric generated always as (length_m * width_m) stored
);

-- ---------------------------------------------------------------------------------------------
-- Rules, validation runs and findings
-- ---------------------------------------------------------------------------------------------

create table proofpath.rules (
  id                     uuid primary key default gen_random_uuid(),
  rule_code              text not null,
  version                int not null default 1,
  title                  text,
  description            text,
  check_type             text not null,
  params                 jsonb not null default '{}',
  categories             text[],
  source_reference       text,
  clause                 text,
  severity               text,
  requires_human_review  boolean not null default true,
  status                 text not null default 'draft' check (status in ('draft', 'pending_approval', 'active', 'retired')),
  effective_from         date,
  effective_to           date,
  created_by             uuid references proofpath.members (user_id),
  approved_by            uuid references proofpath.members (user_id),
  approved_at            timestamptz,
  note                   text not null default 'Illustrative demo rule, not an official AICTE rule',
  unique (rule_code, version),
  -- Four eyes: whoever approves a rule did not write it
  check (approved_by is null or created_by is null or approved_by <> created_by)
);

create table proofpath.comparison_pairs (
  id            uuid primary key default gen_random_uuid(),
  pair_code     text unique not null,
  rule_code     text,
  finding_type  text,
  doc_type_a    text references proofpath.document_types (code),
  field_a       text,
  doc_type_b    text references proofpath.document_types (code),
  field_b       text,
  label         text
);

create table proofpath.validation_runs (
  id              uuid primary key default gen_random_uuid(),
  application_id  uuid references proofpath.applications (id) on delete cascade,
  mode            text check (mode in ('full', 'preflight', 'dry_run')),
  as_of_date      date,
  rule_versions   jsonb,
  started_by      uuid,
  started_at      timestamptz not null default now(),
  finished_at     timestamptz,
  summary         jsonb
);

create table proofpath.findings (
  id                      uuid primary key default gen_random_uuid(),
  finding_key             text unique not null,
  application_id          uuid not null references proofpath.applications (id) on delete cascade,
  related_application_id  uuid references proofpath.applications (id),
  finding_type            text not null,
  rule_code               text,
  rule_version            int,
  severity                text check (severity in ('info', 'low', 'medium', 'high')),
  title                   text,
  detail                  text,
  status                  text not null default 'open' check (status in ('open', 'evidence_requested', 'resolved', 'dismissed', 'auto_closed')),
  is_cross_institution    boolean not null default false,
  first_run_id            uuid references proofpath.validation_runs (id),
  last_run_id             uuid references proofpath.validation_runs (id),
  created_at              timestamptz not null default now()
);

create table proofpath.finding_evidence (
  id           uuid primary key default gen_random_uuid(),
  finding_id   uuid not null references proofpath.findings (id) on delete cascade,
  document_id  uuid references proofpath.documents (id),
  page_number  int,
  role         text check (role in ('A', 'B', 'SINGLE')),
  label        text,
  shown_value  text,
  bbox         jsonb
);

create table proofpath.review_actions (
  id          uuid primary key default gen_random_uuid(),
  finding_id  uuid references proofpath.findings (id) on delete cascade,
  field_id    uuid references proofpath.extracted_fields (id) on delete cascade,
  actor_id    uuid references proofpath.members (user_id),
  actor_role  text,
  action      text not null check (action in ('resolve', 'dismiss', 'request_evidence', 'confirm_field', 'correct_field')),
  reason      text not null check (length(trim(reason)) > 0),
  created_at  timestamptz not null default now()
);

create table proofpath.evidence_requests (
  id                        uuid primary key default gen_random_uuid(),
  finding_id                uuid references proofpath.findings (id),
  application_id            uuid references proofpath.applications (id),
  requested_by              uuid,
  message                   text,
  due_date                  date,
  status                    text not null default 'open' check (status in ('open', 'fulfilled', 'cancelled')),
  fulfilled_by_document_id  uuid references proofpath.documents (id),
  created_at                timestamptz not null default now()
);

create table proofpath.verification_checks (
  id           uuid primary key default gen_random_uuid(),
  document_id  uuid references proofpath.documents (id) on delete cascade,
  method       text check (method in ('HASH', 'SIGNATURE', 'REGISTRY', 'METADATA', 'MANUAL')),
  source       text,
  status       text,
  is_mock      boolean not null default false,
  response     jsonb,
  checked_by   uuid,
  checked_at   timestamptz not null default now()
);

create table proofpath.notifications (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references proofpath.members (user_id) on delete cascade,
  kind        text,
  ref_type    text,
  ref_id      text,
  message     text,
  read_at     timestamptz,
  created_at  timestamptz not null default now()
);

create table proofpath.case_file_snapshots (
  id              uuid primary key default gen_random_uuid(),
  application_id  uuid references proofpath.applications (id),
  generated_by    uuid,
  payload         jsonb,
  created_at      timestamptz not null default now()
);

create table proofpath.priority_weights (key text primary key, weight int not null);
create table proofpath.settings (key text primary key, value jsonb not null);

-- ---------------------------------------------------------------------------------------------
-- Audit: append-only and hash-chained. Each event hashes the previous event's hash plus its own fields.
-- ---------------------------------------------------------------------------------------------

create table proofpath.audit_events (
  id              bigint generated always as identity primary key,
  actor_id        uuid,
  actor_role      text,
  event_type      text not null,
  entity_type     text,
  entity_id       text,
  application_id  uuid,
  detail          jsonb,
  created_at      timestamptz not null,
  prev_hash       text not null,
  event_hash      text not null
);

create function proofpath.audit_block() returns trigger
language plpgsql set search_path = '' as $$
begin
  raise exception 'proofpath.audit_events is append-only';
end; $$;

create trigger audit_no_change before update or delete on proofpath.audit_events
  for each row execute function proofpath.audit_block();
create trigger audit_no_truncate before truncate on proofpath.audit_events
  for each statement execute function proofpath.audit_block();

-- The hash of one event; audit_append writes it and audit_verify recomputes it with the same formula
create function proofpath.audit_hash(p_prev text, p_actor uuid, p_role text, p_type text, p_entity_type text,
  p_entity_id text, p_app uuid, p_detail jsonb, p_ts timestamptz) returns text
-- digest() comes from pgcrypto, which Supabase installs in `extensions` (older projects: `public`)
language sql stable set search_path = extensions, public, pg_temp as $$
  select encode(digest(
    p_prev || '|' || coalesce(p_actor::text, '') || '|' || coalesce(p_role, '') || '|' || p_type || '|' ||
    coalesce(p_entity_type, '') || '|' || coalesce(p_entity_id, '') || '|' || coalesce(p_app::text, '') || '|' ||
    coalesce(p_detail::text, '') || '|' || to_char(p_ts at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS.US'),
    'sha256'), 'hex');
$$;

create function proofpath.audit_append(p_actor uuid, p_role text, p_type text, p_entity_type text,
  p_entity_id text, p_app uuid, p_detail jsonb) returns bigint
language plpgsql set search_path = '' as $$
declare v_prev text; v_ts timestamptz := clock_timestamp(); v_id bigint;
begin
  -- One writer at a time, so two events never chain from the same predecessor
  perform pg_advisory_xact_lock(hashtext('proofpath.audit_events'));
  select event_hash into v_prev from proofpath.audit_events order by id desc limit 1;
  v_prev := coalesce(v_prev, 'GENESIS');
  insert into proofpath.audit_events (actor_id, actor_role, event_type, entity_type, entity_id, application_id, detail,
                                      created_at, prev_hash, event_hash)
  values (p_actor, p_role, p_type, p_entity_type, p_entity_id, p_app, p_detail, v_ts, v_prev,
          proofpath.audit_hash(v_prev, p_actor, p_role, p_type, p_entity_type, p_entity_id, p_app, p_detail, v_ts))
  returning id into v_id;
  return v_id;
end; $$;

-- Recompute every hash in order. Returns ok, the number of events checked, and the first broken event if any.
create function proofpath.audit_verify() returns jsonb
language plpgsql stable set search_path = '' as $$
declare r record; v_prev text := 'GENESIS'; v_n bigint := 0;
begin
  for r in select * from proofpath.audit_events order by id loop
    if r.prev_hash <> v_prev or r.event_hash <> proofpath.audit_hash(r.prev_hash, r.actor_id, r.actor_role, r.event_type,
         r.entity_type, r.entity_id, r.application_id, r.detail, r.created_at) then
      return jsonb_build_object('ok', false, 'events_checked', v_n, 'broken_at_id', r.id);
    end if;
    v_prev := r.event_hash;
    v_n := v_n + 1;
  end loop;
  return jsonb_build_object('ok', true, 'events_checked', v_n, 'broken_at_id', null);
end; $$;

-- The active version of a rule on a date (spec section 9)
create function proofpath.rule_ver(p_code text, p_as_of date) returns int
language sql stable set search_path = '' as $$
  select version from proofpath.rules
  where rule_code = p_code and status = 'active'
    and (effective_from is null or effective_from <= p_as_of)
    and (effective_to is null or effective_to >= p_as_of)
  order by version desc limit 1;
$$;

-- ---------------------------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------------------------

create index on proofpath.members (institution_id);
create index on proofpath.applications (institution_id);
create index on proofpath.documents (application_id, doc_type, status);
create index on proofpath.documents (sha256);
create index on proofpath.extracted_fields (document_id);
create index on proofpath.extracted_fields (field_name, field_value);
create index on proofpath.faculty (application_id);
create index on proofpath.faculty (masked_id);
create index on proofpath.media_assets (phash);
create index on proofpath.findings (application_id, status);
create index on proofpath.finding_evidence (finding_id);
create index on proofpath.review_actions (finding_id);
create index on proofpath.notifications (user_id, read_at);
create index on proofpath.audit_events (application_id);

-- Tables created above, before the default privileges applied to them
grant all on all tables in schema proofpath to service_role;
grant all on all sequences in schema proofpath to service_role;
revoke execute on all functions in schema proofpath from public, anon, authenticated;
grant execute on all functions in schema proofpath to service_role;

-- Private bucket, separate from Nirikshan's `documents` bucket. Uploads go through signed URLs the API issues.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('proofpath-documents', 'proofpath-documents', false, 15 * 1024 * 1024,
        array['application/pdf', 'image/jpeg', 'image/png'])
on conflict (id) do update set public = false, file_size_limit = excluded.file_size_limit,
                               allowed_mime_types = excluded.allowed_mime_types;
