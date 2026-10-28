"""
Signature and file-metadata checks on a PDF (build spec section 10, methods SIGNATURE and METADATA).

SIGNATURE verifies embedded PDF signatures with pyHanko against the certificates in the trust store
(the `trust_store` setting). Results:
  valid            intact, made by a certificate that chains to the trust store, file unchanged since
  invalid          the signed bytes changed, the signature does not verify, or the file was changed
                   after signing in a way the signature does not allow
  untrusted_chain  intact, but the signer's certificate does not chain to the trust store
  unsigned         no signature (a finding only when the document type requires one, check C13)
  unsupported      not a PDF, or a signature pyHanko cannot read: never treated as invalid

METADATA reads indicators only, never a verdict (check C14): modified after the recorded signing
time, created after it was last modified, and revisions added after the last signed one.

Plain Python; no LLM. Fetching revocation data is off, since the trust store is a closed demo set.
"""
import hashlib
import io
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from core.db import db

logger = logging.getLogger("proofpath.forensics")
# pyHanko logs every failed path search as an error with a traceback; the result says it plainly
for name in ("pyhanko", "pyhanko_certvalidator", "pyhanko.sign.validation", "pyhanko.sign.diff_analysis"):
    logging.getLogger(name).setLevel(logging.CRITICAL)

MIME_PDF = "application/pdf"
SIGNING_TOLERANCE = timedelta(minutes=5)


# ------------------------------------------------------------------------------------------------
# Trust store
# ------------------------------------------------------------------------------------------------

def load_certificate(pem_or_der: bytes):
    """An asn1crypto certificate from PEM or DER bytes. Raises ValueError if it is not one."""
    from asn1crypto import pem, x509
    try:
        der = pem.unarmor(pem_or_der)[2] if pem.detect(pem_or_der) else pem_or_der
        cert = x509.Certificate.load(der)
        cert.native                                   # parse now, so a bad file fails here
        return cert
    except Exception as exc:
        raise ValueError("This is not an X.509 certificate in PEM or DER form") from exc


def describe(cert) -> dict:
    from asn1crypto import pem
    validity = cert["tbs_certificate"]["validity"]
    return {
        "subject": cert.subject.human_friendly, "issuer": cert.issuer.human_friendly,
        "fingerprint": hashlib.sha256(cert.dump()).hexdigest(),
        "not_before": validity["not_before"].native.date().isoformat(),
        "not_after": validity["not_after"].native.date().isoformat(),
        "is_ca": bool(cert.ca), "pem": pem.armor("CERTIFICATE", cert.dump()).decode(),
    }


def trust_store() -> list[dict]:
    try:
        row = db.fetch_one("settings", key="trust_store")
    except Exception:
        return []
    value = (row or {}).get("value") or {}
    return value.get("certificates", []) if isinstance(value, dict) else []


def _roots(entries: list[dict]) -> list:
    out = []
    for e in entries:
        try:
            out.append(load_certificate(e["pem"].encode()))
        except (KeyError, ValueError):
            logger.warning("Skipping an unreadable trust store entry")
    return out


# ------------------------------------------------------------------------------------------------
# Checks
# ------------------------------------------------------------------------------------------------

def _pdf_date(value) -> Optional[datetime]:
    """A PDF date string (D:YYYYMMDDHHmmSS+HH'mm') as an aware datetime, or None."""
    if not value:
        return None
    s = str(value)
    if s.startswith("D:"):
        s = s[2:]
    try:
        base = datetime.strptime(s[:14].ljust(14, "0"), "%Y%m%d%H%M%S")
    except ValueError:
        return None
    rest = s[14:].replace("'", "")
    if rest[:1] in ("+", "-") and len(rest) >= 5:
        sign = 1 if rest[0] == "+" else -1
        offset = timedelta(hours=int(rest[1:3]), minutes=int(rest[3:5]))
        return (base - sign * offset).replace(tzinfo=timezone.utc)
    return base.replace(tzinfo=timezone.utc)


def check_signature(data: bytes, mime: str, trusted: Optional[list[dict]] = None) -> dict:
    """The SIGNATURE result for one file: {status, note, signatures: [...]}. Never raises."""
    if mime != MIME_PDF:
        return {"status": "unsupported", "note": "Only PDF files carry an embedded digital signature", "signatures": []}
    try:
        from pyhanko.pdf_utils.reader import PdfFileReader
        from pyhanko.sign.validation import validate_pdf_signature
        from pyhanko_certvalidator import ValidationContext

        reader = PdfFileReader(io.BytesIO(data), strict=False)
        embedded = reader.embedded_signatures
    except Exception:
        logger.info("Signature reading failed", exc_info=True)
        return {"status": "unsupported", "note": "The file's signature structure could not be read", "signatures": []}
    if not embedded:
        return {"status": "unsigned", "note": "The file carries no digital signature", "signatures": []}

    roots = _roots(trust_store() if trusted is None else trusted)
    results = []
    for sig in embedded:
        entry = {"field": sig.field_name, "signed_revision": sig.signed_revision}
        try:
            context = ValidationContext(trust_roots=roots, allow_fetching=False, revocation_mode="soft-fail")
            st = validate_pdf_signature(sig, context)
            entry.update({
                "signer": st.signing_cert.subject.human_friendly if st.signing_cert else None,
                "signer_issuer": st.signing_cert.issuer.human_friendly if st.signing_cert else None,
                "signed_at": st.signer_reported_dt.isoformat() if st.signer_reported_dt else None,
                "intact": bool(st.intact), "valid": bool(st.valid), "trusted": bool(st.trusted),
                "coverage": st.coverage.name if st.coverage else None,
                "modification_level": st.modification_level.name if st.modification_level else None,
                "changed_after_signing": st.docmdp_ok is False,
            })
            if not st.intact or not st.valid:
                entry["status"], entry["note"] = "invalid", "The signed content does not match the signature"
            elif st.docmdp_ok is False:
                entry["status"], entry["note"] = "invalid", "The file was changed after it was signed, in a way the signature does not allow"
            elif not st.trusted:
                entry["status"], entry["note"] = "untrusted_chain", "The signer's certificate does not chain to a certificate in the trust store"
            else:
                entry["status"], entry["note"] = "valid", "Intact, and signed by a certificate that chains to the trust store"
        except Exception as exc:
            logger.info("Signature validation failed", exc_info=True)
            entry.update({"status": "unsupported", "note": f"The signature could not be checked ({type(exc).__name__})"})
        results.append(entry)

    # The worst signature decides the file's result
    order = ["invalid", "untrusted_chain", "unsupported", "valid"]
    worst = min(results, key=lambda r: order.index(r["status"]))
    return {"status": worst["status"], "note": worst["note"], "signatures": results,
            "total_revisions": reader.xrefs.total_revisions}


def check_metadata(data: bytes, mime: str, signature: Optional[dict] = None) -> dict:
    """The METADATA indicators for one file: {status: clear|indicators|unsupported, indicators, ...}."""
    if mime != MIME_PDF:
        return {"status": "unsupported", "indicators": [], "note": "Only PDF metadata is read"}
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data), strict=False)
        meta = reader.metadata or {}
    except Exception:
        return {"status": "unsupported", "indicators": [], "note": "The file's metadata could not be read"}

    created, modified = _pdf_date(meta.get("/CreationDate")), _pdf_date(meta.get("/ModDate"))
    revisions = (signature or {}).get("total_revisions") or data.count(b"%%EOF")
    indicators = []
    if created and modified and created > modified + SIGNING_TOLERANCE:
        indicators.append({"code": "created_after_modified",
                           "text": f"Creation date {created:%d/%m/%Y %H:%M} is later than modification date {modified:%d/%m/%Y %H:%M} (UTC)"})

    signatures = (signature or {}).get("signatures") or []
    signed_times = [datetime.fromisoformat(s["signed_at"]) for s in signatures if s.get("signed_at")]
    if signed_times and modified and modified > max(signed_times) + SIGNING_TOLERANCE:
        indicators.append({"code": "modified_after_signing",
                           "text": f"Modification date {modified:%d/%m/%Y %H:%M} is later than the signing time {max(signed_times):%d/%m/%Y %H:%M} (UTC)"})
    last_signed = max((s.get("signed_revision") or 0 for s in signatures), default=None)
    if last_signed is not None:
        # Revisions are numbered from 0; the signature's own revision is the last one it covers
        after = revisions - 1 - last_signed
        if after > 0:
            indicators.append({"code": "updated_after_signing",
                               "text": f"{after} revision{'s' if after > 1 else ''} added after the last signature"})
    return {
        "status": "indicators" if indicators else "clear", "indicators": indicators,
        "creation_date": created.isoformat() if created else None, "modification_date": modified.isoformat() if modified else None,
        "producer": str(meta.get("/Producer")) if meta.get("/Producer") else None, "revisions": revisions,
        "note": "Indicators only, shown with what was read; they are not a verdict on the document.",
    }


def record(document: dict, data: bytes, doc_type: dict, actor_id: Optional[str] = None) -> tuple[dict, dict]:
    """Run both checks on a document and store a verification_checks row for each. An image of a
    document type that needs no signature gets no SIGNATURE row."""
    signature = check_signature(data, document["mime"])
    metadata = check_metadata(data, document["mime"], signature)
    rows = []
    if document["mime"] == MIME_PDF or doc_type.get("signature_required"):
        rows.append({"document_id": document["id"], "method": "SIGNATURE", "source": "Embedded PDF signature, trust store",
                     "status": signature["status"], "is_mock": False, "response": signature, "checked_by": actor_id})
    if document["mime"] == MIME_PDF:
        rows.append({"document_id": document["id"], "method": "METADATA", "source": "PDF metadata",
                     "status": metadata["status"], "is_mock": False, "response": metadata, "checked_by": actor_id})
    if rows:
        db.table("verification_checks").insert(rows).execute()
    return signature, metadata
