-- ProofPath AI: values suggested by an AI when no label pattern finds them (services/suggest.py).
--
-- A suggestion is stored with source_method AI_SUGGESTED and review_state needs_confirmation, so no
-- check compares it until a reviewer confirms or corrects it (build spec 1.2, principles 4 and 6).
-- Until this runs, the API drops suggestions and stores the values as before. Safe to run more than once.

alter table proofpath.extracted_fields drop constraint if exists extracted_fields_source_method_check;
alter table proofpath.extracted_fields add constraint extracted_fields_source_method_check
  check (source_method in ('PDF_TEXT', 'OCR', 'MANUAL', 'AI_SUGGESTED'));
