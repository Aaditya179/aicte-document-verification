-- ProofPath AI: phase 4 reference data. Safe to rerun.
--
-- R-REG-01 switches on check C15 (REGISTRY_MISMATCH): the latest issuer-registry answer for a current
-- document gave values that differ from the values read from it. The spec's check catalogue has C15 but
-- its rule list has no rule for it (CLAUDE.md, assumption A30). The issuer registry is a MOCK.
-- Illustrative demo rule, not an official AICTE rule.

insert into proofpath.rules (rule_code, version, title, description, check_type, params, severity, status, effective_from)
values ('R-REG-01', 1, 'Issuer registry agrees',
        'The issuer registry record for a certificate, NOC or land record has the same values as the document. The registry is a MOCK.',
        'registry_match', '{}', 'high', 'active', '2026-01-01')
on conflict (rule_code, version) do nothing;

-- The MOCK registry answers unavailable until a rule administrator changes it (unavailable, match or mismatch)
insert into proofpath.settings (key, value) values ('registry_adapter_mode', '"unavailable"')
on conflict (key) do nothing;
