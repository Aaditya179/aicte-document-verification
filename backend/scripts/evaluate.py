"""
Evaluation against the synthetic ground truth (build spec section 14).

Signs in as the demo reviewer through the REST API, runs a full validation on every seeded application,
and compares the findings with seed/ground_truth.json: true positives, false positives, false negatives,
precision, recall, F1, the result per finding type, and whether anything was flagged on the
applications that must not be.

Run from backend/ with the API running:

    PYTHONPATH=. .venv/bin/python -m scripts.evaluate [--api http://localhost:8001/api/v1] [--out evaluation.txt]

The reviewer account needs DEMO_MFA_BYPASS=true in the API's environment, or an aal2 session.
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import httpx

from core.config import settings

HEADLINE = "Measured on a synthetic dataset; not validated on real AICTE records."
GROUND_TRUTH = Path(__file__).resolve().parents[1] / "seed" / "ground_truth.json"


def _ratio(a: int, b: int) -> float:
    return a / b if b else 1.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default=f"http://localhost:{settings.PORT}/api/v1")
    parser.add_argument("--email", default="reviewer@proofpath.demo")
    parser.add_argument("--out", help="also write the report to this file")
    args = parser.parse_args()

    truth = json.loads(GROUND_TRUTH.read_text())
    client = httpx.Client(base_url=args.api, timeout=120)
    login = client.post("/auth/login", json={"email": args.email, "password": settings.DEMO_PASSWORD})
    login.raise_for_status()
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

    by_code = {a["code"]: a for a in client.get("/applications").raise_for_status().json()}
    lines = [HEADLINE, "", f"Ground truth: {len(truth['applications'])} applications, as-of date {truth['as_of']}.", ""]

    tp, fp, fn = [], [], []
    per_type = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    flagged_clean = []
    for code, spec in sorted(truth["applications"].items()):
        app = by_code.get(code)
        if not app:
            lines.append(f"Missing application {code}: run the seed first.")
            return 2
        client.post(f"/applications/{app['id']}/validate").raise_for_status()
        findings = client.get(f"/applications/{app['id']}/findings").raise_for_status().json()
        got = {f["finding_key"] for f in findings if f["status"] != "auto_closed"}
        expected = set(spec["expected"])
        for key in got & expected:
            tp.append(key); per_type[key.split("|")[0]]["tp"] += 1
        for key in got - expected:
            fp.append(key); per_type[key.split("|")[0]]["fp"] += 1
        for key in expected - got:
            fn.append(key); per_type[key.split("|")[0]]["fn"] += 1
        if not expected and got:
            flagged_clean.append((code, sorted(got)))

    precision, recall = _ratio(len(tp), len(tp) + len(fp)), _ratio(len(tp), len(tp) + len(fn))
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    lines += [
        f"True positives:  {len(tp)}",
        f"False positives: {len(fp)}",
        f"False negatives: {len(fn)}",
        f"Precision {precision:.3f}   Recall {recall:.3f}   F1 {f1:.3f}",
        "",
        "By finding type (true positives / false positives / false negatives):",
    ]
    for kind, c in sorted(per_type.items()):
        lines.append(f"  {kind:<28} {c['tp']:>3} / {c['fp']:>3} / {c['fn']:>3}")
    clean = [c for c, s in truth["applications"].items() if not s["expected"]]
    lines += ["", f"Must not be flagged: {len(clean) - len(flagged_clean)} of {len(clean)} applications had no findings, "
                  f"including the clean control {truth['clean_control']}."]
    for code, keys in flagged_clean:
        lines.append(f"  Flagged: {code}: {', '.join(keys)}")
    for code in truth.get("must_not_flag", []):
        scenario = truth["applications"][code]["scenario"].replace("_", " ")
        flagged = next((k for c, k in flagged_clean if c == code), None)
        lines.append(f"  {code} ({scenario}): {'FLAGGED ' + ', '.join(flagged) if flagged else 'not flagged'}")
    for label, keys in (("False positive", fp), ("False negative", fn)):
        for key in sorted(keys):
            lines.append(f"  {label}: {key}")

    report = "\n".join(lines)
    print(report)
    if args.out:
        Path(args.out).write_text(report + "\n")
    return 0 if not fp and not fn else 1


if __name__ == "__main__":
    sys.exit(main())
