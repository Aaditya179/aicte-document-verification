-- ProofPath AI: phase 3 reference data. Safe to rerun.
--
-- R-GHOST-01 version 2. Version 1's name similarity of 0.7 (the spec's default) matched different people
-- who share a given name: "aditi agarkar" and "aditi rangan" score 72 on RapidFuzz token-sort ratio, and
-- unrelated pairs in the seeded dataset reach 85. Spellings of one name score 94 or more ("rohini deshpande"
-- and "rohini s deshpande" 94, swapped order 100). Version 2 asks for 0.9. Version 1 is retired, not
-- edited, so earlier runs keep the version they recorded. Illustrative demo rule, not an official AICTE rule.

insert into proofpath.rules (rule_code, version, title, description, check_type, params, severity, status, effective_from)
values ('R-GHOST-01', 2, 'Faculty not shared',
        'A faculty member is not listed by another institution for an overlapping period. Same masked ID, or a name at least 90% similar with the same qualification.',
        'ghost_faculty', '{"similarity": 0.9}', 'medium', 'active', '2026-10-28')
on conflict (rule_code, version) do nothing;

update proofpath.rules set status = 'retired', effective_to = '2026-10-27'
where rule_code = 'R-GHOST-01' and version = 1 and status = 'active';
