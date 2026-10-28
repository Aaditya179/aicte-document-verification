-- ProofPath AI: reference data (build spec sections 5.1, 7.4 and 9). Safe to rerun.
--
-- All rules are ILLUSTRATIVE demo rules, not official AICTE rules.
--
-- Extraction templates read the synthetic documents, which print one "Label: value" pair per line,
-- for example "Valid until: 31 March 2028". Patterns are applied per page, case-insensitive and
-- multi-line (services/extraction.py).

insert into proofpath.categories (code, label) values
  ('new_institution', 'New institution'),
  ('extension_of_approval', 'Extension of approval')
on conflict (code) do update set label = excluded.label;

insert into proofpath.document_types (code, label, has_expiry, signature_required, is_photo) values
  ('application_form',     'Application form',       false, false, false),
  ('approval_certificate', 'Approval certificate',   true,  true,  false),
  ('land_document',        'Land document',          false, false, false),
  ('fire_noc',             'Fire NOC',               true,  true,  false),
  ('faculty_list',         'Faculty list',           false, false, false),
  ('affidavit',            'Affidavit',              false, true,  false),
  ('infrastructure_photo', 'Infrastructure photo',   false, false, true),
  ('floor_plan',           'Floor plan',             false, false, false)
on conflict (code) do update set label = excluded.label, has_expiry = excluded.has_expiry,
  signature_required = excluded.signature_required, is_photo = excluded.is_photo;

insert into proofpath.required_documents (category, doc_type) values
  ('new_institution', 'application_form'),
  ('new_institution', 'land_document'),
  ('new_institution', 'fire_noc'),
  ('new_institution', 'faculty_list'),
  ('new_institution', 'affidavit'),
  ('new_institution', 'infrastructure_photo'),
  ('new_institution', 'floor_plan'),
  ('extension_of_approval', 'application_form'),
  ('extension_of_approval', 'approval_certificate'),
  ('extension_of_approval', 'fire_noc'),
  ('extension_of_approval', 'faculty_list'),
  ('extension_of_approval', 'affidavit'),
  ('extension_of_approval', 'infrastructure_photo'),
  ('extension_of_approval', 'floor_plan')
on conflict (category, doc_type) do nothing;

insert into proofpath.extraction_templates (doc_type, field_name, value_type, regex, required) values
  ('application_form', 'institution_code',                 'text',   '^\s*Institution code\s*:\s*([A-Z0-9][A-Z0-9/-]*)', true),
  ('application_form', 'institution_name',                 'text',   '^\s*Institution name\s*:\s*(.+?)\s*$', true),
  ('application_form', 'declared_faculty_count',           'int',    '^\s*Number of faculty\s*:\s*([\d,]+)', true),
  ('application_form', 'declared_total_area_sqm',          'number', '^\s*Total built-up area\s*:\s*([\d,]+(?:\.\d+)?)', true),
  ('application_form', 'declared_certificate_valid_until', 'date',   '^\s*Approval valid until\s*:\s*(.+?)\s*$', false),
  ('application_form', 'declared_fire_noc_no',             'text',   '^\s*Fire NOC (?:no\.?|number)\s*:\s*([A-Z0-9][A-Z0-9/-]*)', false),
  ('application_form', 'survey_no',                        'text',   '^\s*Survey (?:no\.?|number)\s*:\s*([0-9][0-9A-Za-z/ -]*?)\s*$', false),

  ('approval_certificate', 'certificate_no',   'text', '^\s*Certificate (?:no\.?|number)\s*:\s*([A-Z0-9][A-Z0-9/-]*)', true),
  ('approval_certificate', 'institution_code', 'text', '^\s*Institution code\s*:\s*([A-Z0-9][A-Z0-9/-]*)', true),
  ('approval_certificate', 'issue_date',       'date', '^\s*Date of issue\s*:\s*(.+?)\s*$', true),
  ('approval_certificate', 'expiry_date',      'date', '^\s*Valid until\s*:\s*(.+?)\s*$', true),

  ('fire_noc', 'noc_no',      'text', '^\s*NOC (?:no\.?|number)\s*:\s*([A-Z0-9][A-Z0-9/-]*)', true),
  ('fire_noc', 'issue_date',  'date', '^\s*Date of issue\s*:\s*(.+?)\s*$', true),
  ('fire_noc', 'expiry_date', 'date', '^\s*Valid until\s*:\s*(.+?)\s*$', true),

  ('land_document', 'survey_no',       'text',   '^\s*Survey (?:no\.?|number)\s*:\s*([0-9][0-9A-Za-z/ -]*?)\s*$', true),
  ('land_document', 'registration_no', 'text',   '^\s*Registration (?:no\.?|number)\s*:\s*([A-Z0-9][A-Z0-9/-]*)', false),
  ('land_document', 'land_area_sqm',   'number', '^\s*Land area\s*:\s*([\d,]+(?:\.\d+)?)', false),

  ('faculty_list', 'faculty_total', 'int', '^\s*Total faculty\s*:\s*([\d,]+)', true),

  ('affidavit', 'institution_code', 'text', '^\s*Institution code\s*:\s*([A-Z0-9][A-Z0-9/-]*)', true),
  ('affidavit', 'affidavit_date',   'date', '^\s*Date\s*:\s*(.+?)\s*$', true)
on conflict (doc_type, field_name) do update set value_type = excluded.value_type, regex = excluded.regex,
  required = excluded.required;

-- Values that must agree between two documents of one application (check C4)
insert into proofpath.comparison_pairs (pair_code, rule_code, finding_type, doc_type_a, field_a, doc_type_b, field_b, label) values
  ('CERT_VALIDITY',  'R-PAIR-01', 'DATE_CONFLICT',  'application_form', 'declared_certificate_valid_until', 'approval_certificate', 'expiry_date',      'Approval certificate validity'),
  ('INST_CODE',      'R-PAIR-01', 'ID_MISMATCH',    'application_form', 'institution_code',                 'approval_certificate', 'institution_code', 'Institution code'),
  ('FACULTY_COUNT',  'R-PAIR-01', 'COUNT_CONFLICT', 'application_form', 'declared_faculty_count',           'faculty_list',         'faculty_total',    'Faculty count'),
  ('FIRE_NOC_NO',    'R-PAIR-01', 'ID_MISMATCH',    'application_form', 'declared_fire_noc_no',             'fire_noc',             'noc_no',           'Fire NOC number'),
  ('SURVEY_NO',      'R-PAIR-01', 'ID_MISMATCH',    'application_form', 'survey_no',                        'land_document',        'survey_no',        'Land survey number')
on conflict (pair_code) do nothing;

insert into proofpath.rules (rule_code, version, title, description, check_type, params, severity, status, effective_from) values
  ('R-DOC-REQ', 1, 'Required documents', 'Every document the category requires is uploaded and passed the file check.', 'required_document', '{}', 'high', 'active', '2026-01-01'),
  ('R-EXP-01', 1, 'Document in date', 'A document type that expires has an expiry date after the as-of date.', 'expiry', '{}', 'high', 'active', '2026-01-01'),
  ('R-DATE-01', 1, 'Dates in order', 'A document''s expiry date is not before its issue date.', 'date_order', '{}', 'medium', 'active', '2026-01-01'),
  ('R-PAIR-01', 1, 'Documents agree', 'Values that appear in two documents of one application match after normalisation.', 'pair_compare', '{}', 'medium', 'active', '2026-01-01'),
  ('R-DUP-01', 1, 'No duplicate files', 'The same file is not uploaded as two documents of one application.', 'duplicate_file', '{}', 'low', 'active', '2026-01-01'),
  ('R-ID-REUSE', 1, 'Identifiers not reused', 'A certificate, NOC, registration or survey number does not appear in another institution''s application.', 'reused_identifier', '{}', 'medium', 'active', '2026-01-01'),
  ('R-GHOST-01', 1, 'Faculty not shared', 'A faculty member is not listed by another institution for an overlapping period.', 'ghost_faculty', '{"similarity": 0.7}', 'medium', 'active', '2026-01-01'),
  ('R-PHOTO-01', 1, 'Photos not reused', 'An infrastructure photo is not a copy of another institution''s photo.', 'photo_reuse', '{"max_hamming": 8}', 'medium', 'active', '2026-01-01'),
  ('R-INFRA-01', 1, 'Infrastructure evidence', 'Photos of a lab, a classroom and the library, and a floor plan, are all present.', 'infra_evidence', '{"required": ["lab", "classroom", "library", "floor_plan"]}', 'high', 'active', '2026-01-01'),
  ('R-AREA-01', 1, 'Built-up area', 'Room areas add up to the declared total within tolerance, and the total meets the minimum.', 'area_check', '{"area_tolerance_pct": 1, "min_area_sqm": 4000}', 'medium', 'active', '2026-01-01'),
  ('R-PHOTOAGE-01', 1, 'Recent photos', 'Infrastructure photos were taken within the last 12 months.', 'photo_metadata', '{"max_photo_age_months": 12}', 'low', 'active', '2026-01-01'),
  ('R-SIG-01', 1, 'Signed documents', 'Document types that require a signature carry a valid one.', 'signature_required', '{}', 'medium', 'active', '2026-01-01'),
  ('R-META-01', 1, 'File metadata', 'A PDF was not changed after it was signed, and its dates are in order.', 'metadata_check', '{}', 'low', 'active', '2026-01-01'),
  ('R-OCR-01', 1, 'Readable values', 'A value read by OCR below this confidence goes to a reviewer to confirm.', 'extraction', '{"min_confidence": 0.80}', 'low', 'active', '2026-01-01')
on conflict (rule_code, version) do nothing;

insert into proofpath.priority_weights (key, weight) values
  ('missing_document', 30),
  ('expired_document', 25),
  ('infra_evidence_missing', 25),
  ('cross_institution', 25),
  ('conflict', 20),
  ('area', 20),
  ('signature_or_registry', 30),
  ('needs_confirmation', 10),
  ('duplicate', 10),
  ('metadata', 5)
on conflict (key) do nothing;

insert into proofpath.settings (key, value) values
  ('registry_adapter_mode', '"unavailable"')   -- MOCK issuer registry: unavailable, match or mismatch
on conflict (key) do nothing;
