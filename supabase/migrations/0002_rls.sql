-- ProofPath AI: row-level security (build spec section 5.2, as adapted in CLAUDE.md, assumption D4).
--
-- The browser never reads or writes `proofpath` tables. It uses Supabase only for sign-in, MFA and
-- uploading a file to a signed URL the API issued. So instead of per-role policies, every table has
-- RLS on with no policies, and `anon` and `authenticated` get no privileges at all. Only the API's
-- service role (which bypasses RLS) can reach the data, and the API enforces each role's access
-- (core/access.py, tested in tests/test_access.py).

do $$
declare t record;
begin
  for t in select tablename from pg_tables where schemaname = 'proofpath' loop
    execute format('alter table proofpath.%I enable row level security', t.tablename);
    execute format('revoke all on proofpath.%I from anon, authenticated', t.tablename);
  end loop;
end $$;

revoke all on schema proofpath from anon, authenticated;
revoke all on all sequences in schema proofpath from anon, authenticated;
revoke execute on all functions in schema proofpath from public, anon, authenticated;

-- Fail loudly if anything is still open to a browser role
do $$
declare n int;
begin
  select count(*) into n from information_schema.role_table_grants
  where table_schema = 'proofpath' and grantee in ('anon', 'authenticated', 'PUBLIC');
  if n > 0 then
    raise exception 'proofpath still grants % table privilege(s) to a browser role', n;
  end if;

  select count(*) into n from pg_tables where schemaname = 'proofpath' and not rowsecurity;
  if n > 0 then
    raise exception '% proofpath table(s) without row-level security', n;
  end if;
end $$;

-- Storage: the bucket is private, and ProofPath adds no storage policies. Objects are read and
-- written only through short-lived signed URLs created by the service role, so Nirikshan's
-- storage policies on its own `documents` bucket are untouched.
--
-- A storage policy that does not name a bucket would also open `proofpath-documents`. Warn about any.
do $$
declare p record;
begin
  for p in select policyname from pg_policies
           where schemaname = 'storage' and tablename = 'objects'
             and coalesce(qual, '') not like '%bucket_id%' and coalesce(with_check, '') not like '%bucket_id%' loop
    raise warning 'storage policy "%" does not filter by bucket and may expose proofpath-documents', p.policyname;
  end loop;
end $$;
