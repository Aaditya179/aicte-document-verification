-- ProofPath AI: wider label wording for reading values (extraction templates).
--
-- Each template matched one wording only ("Date of issue", "Valid until", "NOC no"), so a document
-- that says "Issue Date", "Expiry Date" or, on a Fire NOC, "Certificate Number" was read as not found.
-- These patterns accept the common variants of each label. The value part of every pattern is
-- unchanged, and the seeded documents still read the same (backend/tests/test_label_variants.py).
-- A label may be followed by ":" or "-". Safe to run more than once.

update proofpath.extraction_templates as t set regex = v.regex
from (values
  -- Application form
  ('application_form', 'institution_code',
   '^\s*(?:Institution|Institute) code\s*[:-]\s*([A-Z0-9][A-Z0-9/ .-]*?)\s*$'),
  ('application_form', 'institution_name',
   '^\s*(?:Institution|Institute) name\s*[:-]\s*(.+?)\s*$'),
  ('application_form', 'declared_faculty_count',
   '^\s*(?:Number of faculty|No\.? of faculty|Total faculty|Faculty (?:count|strength))\s*[:-]\s*([\d,]+)'),
  ('application_form', 'declared_total_area_sqm',
   '^\s*(?:Total )?built[- ]up area(?: \(sq\.? ?m\))?\s*[:-]\s*([\d,]+(?:\.\d+)?)'),
  ('application_form', 'declared_certificate_valid_until',
   '^\s*Approval (?:valid (?:until|till|up ?to)|validity|expiry date)\s*[:-]\s*(.+?)\s*$'),
  ('application_form', 'declared_fire_noc_no',
   '^\s*Fire NOC (?:no\.?|number|certificate (?:no\.?|number))\s*[:-]\s*([A-Z0-9][A-Z0-9/ .-]*?)\s*$'),
  ('application_form', 'survey_no',
   '^\s*Survey (?:no\.?|number)\s*[:-]\s*([0-9][0-9A-Za-z/ -]*?)\s*$'),

  -- Approval certificate
  ('approval_certificate', 'certificate_no',
   '^\s*(?:Approval )?Certificate (?:no\.?|number)\s*[:-]\s*([A-Z0-9][A-Z0-9/ .-]*?)\s*$'),
  ('approval_certificate', 'institution_code',
   '^\s*(?:Institution|Institute) code\s*[:-]\s*([A-Z0-9][A-Z0-9/ .-]*?)\s*$'),
  ('approval_certificate', 'issue_date',
   '^\s*(?:Date of issue|Issue date|Date of issuance|Issued on)\s*[:-]\s*(.+?)\s*$'),
  ('approval_certificate', 'expiry_date',
   '^\s*(?:Valid (?:until|till|up ?to)|Validity|Expiry date|Date of expiry|Expires on)\s*[:-]\s*(.+?)\s*$'),

  -- Fire NOC: its number is often printed as the certificate number
  ('fire_noc', 'noc_no',
   '^\s*(?:(?:Fire )?NOC|Certificate) (?:no\.?|number)\s*[:-]\s*([A-Z0-9][A-Z0-9/ .-]*?)\s*$'),
  ('fire_noc', 'issue_date',
   '^\s*(?:Date of issue|Issue date|Date of issuance|Issued on)\s*[:-]\s*(.+?)\s*$'),
  ('fire_noc', 'expiry_date',
   '^\s*(?:Valid (?:until|till|up ?to)|Validity|Expiry date|Date of expiry|Expires on)\s*[:-]\s*(.+?)\s*$'),

  -- Land document
  ('land_document', 'survey_no',
   '^\s*Survey (?:no\.?|number)\s*[:-]\s*([0-9][0-9A-Za-z/ -]*?)\s*$'),
  ('land_document', 'registration_no',
   '^\s*Registration (?:no\.?|number)\s*[:-]\s*([A-Z0-9][A-Z0-9/ .-]*?)\s*$'),
  ('land_document', 'land_area_sqm',
   '^\s*(?:Land area|Total land area|Area of land)(?: \(sq\.? ?m\))?\s*[:-]\s*([\d,]+(?:\.\d+)?)'),

  -- Faculty list
  ('faculty_list', 'faculty_total',
   '^\s*(?:Total faculty|Total number of faculty|Faculty total|Number of faculty)\s*[:-]\s*([\d,]+)'),

  -- Affidavit
  ('affidavit', 'institution_code',
   '^\s*(?:Institution|Institute) code\s*[:-]\s*([A-Z0-9][A-Z0-9/ .-]*?)\s*$'),
  ('affidavit', 'affidavit_date',
   '^\s*(?:Date|Dated|Date of affidavit)\s*[:-]\s*(.+?)\s*$')
) as v(doc_type, field_name, regex)
where t.doc_type = v.doc_type and t.field_name = v.field_name;
