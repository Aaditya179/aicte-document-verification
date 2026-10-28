"""
Digital signatures for the seeded documents (checks C13 and C14). Everything here is FICTIONAL.

A demo root CA, "ProofPath Demo Root CA (fictional)", issues one signing certificate per issuer: the
approval register, the fire services and a notary. The seed puts the root in the trust store, so their
signatures read as valid. A separate self-signed certificate, not in the trust store, signs the
untrusted-chain scenario.

Keys are made on the first run and kept in seed/generated/pki (git-ignored), so later runs reuse them
and earlier signatures stay valid. They are demo keys for fictional issuers, never real ones.
"""
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pymupdf
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

PKI = Path(__file__).parent / "generated" / "pki"
ROOT = "root"
SIGNERS = {
    "approval": "AICTE approval register signer (fictional)",
    "fire": "State fire services signer (fictional)",
    "notary": "Notary public signer (fictional)",
}
UNLISTED = "unlisted"
SIGNED_BY = {"approval_certificate": "approval", "fire_noc": "fire", "affidavit": "notary"}


def _name(cn: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn),
                      x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Fictional demo issuer, ProofPath AI")])


def _usage(ca: bool) -> x509.KeyUsage:
    return x509.KeyUsage(digital_signature=True, content_commitment=not ca, key_encipherment=False, data_encipherment=False,
                         key_agreement=False, key_cert_sign=ca, crl_sign=ca, encipher_only=False, decipher_only=False)


def _make(cn: str, issuer: tuple | None, ca: bool):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    builder = (x509.CertificateBuilder().subject_name(_name(cn)).public_key(key.public_key())
               .issuer_name(issuer[1].subject if issuer else _name(cn)).serial_number(x509.random_serial_number())
               .not_valid_before(start).not_valid_after(start + timedelta(days=3650))
               .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
               .add_extension(_usage(ca), critical=True))
    return key, builder.sign(issuer[0] if issuer else key, hashes.SHA256())


def _save(name: str, key, cert) -> None:
    PKI.mkdir(parents=True, exist_ok=True)
    (PKI / f"{name}.key").write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                        serialization.NoEncryption()))
    (PKI / f"{name}.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def _load(name: str):
    key = serialization.load_pem_private_key((PKI / f"{name}.key").read_bytes(), password=None)
    return key, x509.load_pem_x509_certificate((PKI / f"{name}.pem").read_bytes())


def ensure() -> None:
    """Make the fictional root, issuers and the unlisted signer once."""
    if (PKI / f"{ROOT}.pem").exists():
        return
    root = _make("ProofPath Demo Root CA (fictional)", None, ca=True)
    _save(ROOT, *root)
    for name, cn in SIGNERS.items():
        _save(name, *_make(cn, root, ca=False))
    _save(UNLISTED, *_make("Unlisted signing certificate (fictional)", None, ca=False))


def root_pem() -> bytes:
    ensure()
    return (PKI / f"{ROOT}.pem").read_bytes()


def _signer(name: str):
    from asn1crypto import keys as akeys, x509 as ax509
    from pyhanko.sign import signers
    from pyhanko_certvalidator.registry import SimpleCertificateStore
    ensure()
    key, cert = _load(name)
    chain = [] if name == UNLISTED else [_load(ROOT)[1]]
    der = lambda c: ax509.Certificate.load(c.public_bytes(serialization.Encoding.DER))  # noqa: E731
    return signers.SimpleSigner(
        signing_cert=der(cert),
        signing_key=akeys.PrivateKeyInfo.load(key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
                                                                serialization.NoEncryption())),
        cert_registry=SimpleCertificateStore.from_certs([der(c) for c in chain]),
    )


def sign(data: bytes, name: str) -> bytes:
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import signers
    out = io.BytesIO()
    signers.sign_pdf(IncrementalPdfFileWriter(io.BytesIO(data)), signers.PdfSignatureMetadata(field_name="IssuerSignature"),
                     signer=_signer(name), output=out)
    return out.getvalue()


def change_after_signing(signed: bytes, altered: bytes) -> bytes:
    """Append a revision that swaps the first page's content for the altered document's, the way a file
    edited after signing looks: the signed revision is intact, the shown page is not the signed one."""
    from pyhanko.pdf_utils import generic
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    content = pymupdf.open(stream=altered, filetype="pdf")[0].read_contents()
    writer = IncrementalPdfFileWriter(io.BytesIO(signed))
    page = writer.root["/Pages"]["/Kids"][0].get_object()
    page["/Contents"] = writer.add_object(generic.StreamObject(stream_data=content))
    writer.update_container(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def set_dates(data: bytes, created: str, modified: str) -> bytes:
    """Rewrite the PDF's creation and modification dates (PDF date strings)."""
    doc = pymupdf.open(stream=data, filetype="pdf")
    keep = {k: v for k, v in doc.metadata.items() if k in ("title", "author", "subject", "keywords", "creator", "producer")}
    doc.set_metadata({**keep, "creationDate": created, "modDate": modified})
    return doc.tobytes(garbage=3, deflate=True, no_new_id=True)
