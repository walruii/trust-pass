"""
Combines the outputs of Modules 1-4 into a single 0-100 "fake probability"
score plus a human-readable list of reasons, so a border officer sees a
verdict band ("Likely Genuine" / "Suspicious -- manual review" / "High
Risk -- likely tampered") and exactly which checks drove it.

Weighting rationale (tune these against real labeled data before any
real deployment -- these starting weights just reflect how strong a
tamper signal each check typically is in practice):

  - Failed MRZ checksum(s)      -> very strong signal (40 pts, scales with # failed)
  - MRZ missing/unparseable     -> strong signal, but could just be bad OCR (15 pts)
  - Expired document            -> policy fact, not forgery evidence (10 pts)
  - Other field validation fail -> moderate (5 pts each, capped)
  - ELA hot regions found       -> strong photo/text tamper signal (up to 25 pts)
  - Copy-move duplication found -> strong signal (15 pts)
  - Editing-software EXIF tag   -> strong signal (15 pts)
  - Missing EXIF entirely       -> weak signal, very common & normal (3 pts)
  - Face mismatch               -> strong identity-fraud signal (up to 20 pts)
"""

def score(mrz_result, validation_result, tamper_result, face_result=None):
    points = 0.0
    reasons = []
    cap = 100.0

    # --- MRZ checksum evidence ---
    if not mrz_result.valid_format:
        points += 15
        reasons.append("MRZ zone could not be located/parsed from the image (poor scan, or MRZ absent/altered).")
    else:
        failed = mrz_result.failed_checks
        if failed:
            points += min(40, 12 * len(failed))
            for f in failed:
                reasons.append(
                    f"MRZ checksum mismatch on '{f.field}': expected check digit {f.expected_check_digit}, "
                    f"found '{f.found_check_digit}'. This field may have been altered after issuance."
                )

    # --- Field validation evidence ---
    val_issues = validation_result.get("issues", [])
    expired = [i for i in val_issues if i.startswith("Document expired")]
    other_issues = [i for i in val_issues if i not in expired]
    if expired:
        points += 10
        reasons.append(expired[0] + " (expired documents are auto-flagged for manual review, independent of forgery risk.)")
    if other_issues:
        points += min(20, 5 * len(other_issues))
        reasons.extend(other_issues)

    # --- Tampering detection evidence ---
    ela = tamper_result.get("error_level_analysis", {})
    regions = ela.get("suspicious_regions", [])
    if regions:
        n = len(regions)
        points += min(25, 8 * n)
        reasons.append(
            f"Error Level Analysis found {n} region(s) with a compression signature inconsistent with the rest "
            f"of the image (possible photo replacement or text edit)."
        )

    meta = tamper_result.get("metadata", {})
    for flag in meta.get("flags", []):
        if "editing tool" in flag:
            points += 15
        elif "re-saved" in flag:
            points += 8
        else:
            points += 3
        reasons.append(flag)

    copy_move = tamper_result.get("copy_move", {})
    if copy_move.get("duplicated_regions_found"):
        points += 15
        reasons.append(
            f"Copy-move analysis found {copy_move.get('inlier_count')} keypoint matches consistent with a single "
            f"geometric transform between two regions of the same image -- possible duplicated/pasted content "
            f"(e.g. a copied stamp)."
        )

    # --- Face verification evidence ---
    if face_result and face_result.get("similarity") is not None:
        sim = face_result["similarity"]
        if not face_result.get("match"):
            points += 20
            reasons.append(
                f"Face similarity between document photo and live capture is low ({sim:.2f}) -- "
                f"possible photo substitution or identity impersonation."
            )
    elif face_result and not face_result.get("doc_face_found"):
        points += 5
        reasons.append("No face could be detected in the document photo region.")

    points = min(points, cap)

    if points < 20:
        verdict = "Likely Genuine"
    elif points < 50:
        verdict = "Suspicious -- Manual Review Recommended"
    else:
        verdict = "High Risk -- Likely Tampered/Fake"

    if not reasons:
        reasons.append("No tampering or validation issues detected by any module.")

    return {
        "fake_probability_percent": round(points, 1),
        "genuine_probability_percent": round(100 - points, 1),
        "verdict": verdict,
        "reasons": reasons,
    }
