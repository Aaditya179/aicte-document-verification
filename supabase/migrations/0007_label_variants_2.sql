-- ProofPath AI: more label wording for reading values, after testing with institution-style files.
--
-- 0006 still missed: labels with a "Declared" prefix on the application form ("Declared Faculty Count"),
-- a unit after the label ("Total Area (sq m)"), and survey numbers that start with letters
-- ("SY-DEMO-448/2"). The seeded documents still read the same (backend/tests/test_label_variants.py).
-- Safe to run more than once.

update proofpath.extraction_templates as t set regex = v.regex
from (values
  ('application_form', 'institution_code',
   '^\s*(?:Declared )?(?:Institution|Institute) code\s*[:-]\s*([A-Z0-9][A-Z0-9/ .-]*?)\s*$'),
  ('application_form', 'institution_name',
   '^\s*(?:Declared )?(?:Institution|Institute) name\s*[:-]\s*(.+?)\s*$'),
  ('application_form', 'declared_faculty_count',
   '^\s*(?:Declared )?(?:Number of faculty|No\.? of faculty|Total faculty|Faculty (?:count|strength))\s*[:-]\s*([\d,]+)'),
  ('application_form', 'declared_total_area_sqm',
   '^\s*(?:Declared )?(?:Total )?(?:built[- ]up )?area(?:\s*\((?:sq\.?\s*m\.?|sqm|m2|m²)\))?\s*[:-]\s*([\d,]+(?:\.\d+)?)'),
  ('application_form', 'declared_certificate_valid_until',
   '^\s*(?:Declared )?Approval (?:certificate )?(?:valid (?:until|till|up ?to)|validity|expiry date)\s*[:-]\s*(.+?)\s*$'),
  ('application_form', 'declared_fire_noc_no',
   '^\s*(?:Declared )?Fire NOC (?:no\.?|number|certificate (?:no\.?|number))\s*[:-]\s*([A-Z0-9][A-Z0-9/ .-]*?)\s*$'),
  ('application_form', 'survey_no',
   '^\s*(?:Declared )?(?:Land )?Survey (?:no\.?|number)\s*[:-]\s*([A-Z0-9][A-Z0-9/ .-]*?)\s*$'),

  ('land_document', 'survey_no',
   '^\s*(?:Land )?Survey (?:no\.?|number)\s*[:-]\s*([A-Z0-9][A-Z0-9/ .-]*?)\s*$'),
  ('land_document', 'land_area_sqm',
   '^\s*(?:Land area|Total land area|Area of land)(?:\s*\((?:sq\.?\s*m\.?|sqm|m2|m²)\))?\s*[:-]\s*([\d,]+(?:\.\d+)?)')
) as v(doc_type, field_name, regex)
where t.doc_type = v.doc_type and t.field_name = v.field_name;
