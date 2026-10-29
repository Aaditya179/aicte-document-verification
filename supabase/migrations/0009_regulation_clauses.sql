-- ProofPath AI: a library of regulation clauses, retrieved for each finding (services/clauses.py).
--
-- A reviewer sees which clauses the rule behind a finding rests on, and can ask for a two-sentence draft
-- explanation written only from the finding, its evidence and those clauses. The seeded clauses are
-- ILLUSTRATIVE, written for this prototype: they are not official AICTE text, and the screens say so.
-- A rule administrator can add clauses with their source. Safe to run more than once.

create table if not exists proofpath.regulation_clauses (
  id               uuid primary key default gen_random_uuid(),
  clause_ref       text not null unique,          -- e.g. "ILL-3.2"
  source           text not null,                 -- where the text comes from
  heading          text not null,
  body             text not null,
  rule_codes       text[] not null default '{}',  -- rules this clause backs, a hint for retrieval
  is_illustrative  boolean not null default true,
  created_by       uuid references proofpath.members (user_id),
  created_at       timestamptz not null default now()
);

alter table proofpath.regulation_clauses enable row level security;
revoke all on proofpath.regulation_clauses from anon, authenticated;
grant all on proofpath.regulation_clauses to service_role;

insert into proofpath.regulation_clauses (clause_ref, source, heading, body, rule_codes) values
  ('ILL-1.1', 'Illustrative handbook for this prototype', 'Documents to accompany an application',
   'Every application shall be accompanied by the documents listed for its category, including the application form, the current approval certificate where one exists, a fire safety no objection certificate, the land document, the list of faculty and an affidavit. A document that cannot be opened or is not of the stated type is treated as not submitted.',
   '{R-DOC-REQ}'),
  ('ILL-1.2', 'Illustrative handbook for this prototype', 'Certificates in force',
   'A certificate or no objection certificate relied on in an application shall be in force on the date the application is examined. A certificate whose validity has ended is to be replaced by a current one.',
   '{R-EXP-01}'),
  ('ILL-1.3', 'Illustrative handbook for this prototype', 'Dates on a certificate',
   'The date until which a certificate is valid shall fall after the date on which it was issued. A certificate whose dates are out of order is referred to the scrutiny officer.',
   '{R-DATE-01}'),
  ('ILL-1.4', 'Illustrative handbook for this prototype', 'Consistency between documents',
   'Particulars stated in the application form, such as the institution code, the number of faculty, the validity of approval, the fire safety certificate number and the land survey number, shall agree with the same particulars in the supporting documents.',
   '{R-PAIR-01}'),
  ('ILL-1.5', 'Illustrative handbook for this prototype', 'One file for each document',
   'Each document shall be uploaded as its own file. The same file shall not be submitted in place of two different documents.',
   '{R-DUP-01}'),
  ('ILL-1.6', 'Illustrative handbook for this prototype', 'Legible particulars',
   'Particulars shall be legible. Where a value cannot be read with confidence, or a date can be read in more than one way, the scrutiny officer confirms it against the document before relying on it.',
   '{R-OCR-01}'),
  ('ILL-2.1', 'Illustrative handbook for this prototype', 'Identifiers unique to one institution',
   'A certificate number, no objection certificate number, registration number or land survey number belongs to one institution. The same identifier appearing in the application of another institution is referred for scrutiny.',
   '{R-ID-REUSE}'),
  ('ILL-2.2', 'Illustrative handbook for this prototype', 'Faculty counted once',
   'A faculty member shall be counted by one institution for any period of employment. A person listed by two institutions for overlapping periods is referred for scrutiny, with the periods and identifiers shown.',
   '{R-GHOST-01}'),
  ('ILL-2.3', 'Illustrative handbook for this prototype', 'Photographs of the premises',
   'Photographs submitted as evidence of infrastructure shall be of the applicant institution''s own premises. A photograph matching one submitted by another institution is referred for scrutiny.',
   '{R-PHOTO-01}'),
  ('ILL-3.1', 'Illustrative handbook for this prototype', 'Evidence of infrastructure',
   'The application shall include recent photographs of at least one laboratory, one classroom and the library, and a floor plan of the built-up area.',
   '{R-INFRA-01}'),
  ('ILL-3.2', 'Illustrative handbook for this prototype', 'Built-up area',
   'The total built-up area declared in the application shall agree, within the stated tolerance, with the sum of the room areas shown on the floor plan, and shall not be less than the minimum built-up area set for the programme.',
   '{R-AREA-01}'),
  ('ILL-3.3', 'Illustrative handbook for this prototype', 'Recent photographs',
   'Photographs of the premises shall have been taken within twelve months before the date of examination. The date a photograph was taken is read from the file where the file records it.',
   '{R-PHOTOAGE-01}'),
  ('ILL-4.1', 'Illustrative handbook for this prototype', 'Digitally signed certificates',
   'Certificates that the issuing authority signs digitally shall carry a signature that verifies and chains to a trusted issuing authority. A certificate of such a type submitted without a signature, or with one that does not verify, is referred for scrutiny.',
   '{R-SIG-01}'),
  ('ILL-4.2', 'Illustrative handbook for this prototype', 'Integrity of electronic documents',
   'An electronic document shall not be altered after it is signed. Indications from the file, such as changes after signing or creation and modification dates out of order, are recorded for the scrutiny officer as indicators, not as findings of fact.',
   '{R-META-01}'),
  ('ILL-4.3', 'Illustrative handbook for this prototype', 'Confirmation with the issuer',
   'Where the issuing authority maintains a register of the certificates it issues, the particulars of a submitted certificate may be compared with that register. A difference is referred for scrutiny; an unavailable register is not a difference.',
   '{R-REG-01}'),
  ('ILL-5.1', 'Illustrative handbook for this prototype', 'Decision on an application',
   'Scrutiny records what was found and where. The decision on an application rests with the authorised official, who considers the findings together with the institution''s response.',
   '{}')
on conflict (clause_ref) do nothing;
