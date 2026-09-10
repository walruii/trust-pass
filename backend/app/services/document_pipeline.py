import cv2

from app.services import document_ocr as ocr
from app.services import face_module, mrz, risk_scorer, tamper_detection, validation


def analyze_document(image_path: str, selfie_path: str = None) -> dict:
    image_bgr = cv2.imread(image_path)
    if image_bgr is None:
        return {"error": f"Could not read image at {image_path}. Ensure it's a valid JPG/PNG."}

    ocr_result = ocr.extract_all(image_bgr)
    mrz_result = mrz.parse_td3_mrz(ocr_result["mrz_text"])
    merged_fields = ocr.extract_document_fields(image_bgr, mrz_result)
    validation_result = validation.validate_fields(mrz_result)
    tamper_result = tamper_detection.run_all(image_bgr, image_path)

    face_result = None
    if selfie_path:
        selfie_bgr = cv2.imread(selfie_path)
        if selfie_bgr is not None:
            face_result = face_module.compare_faces(image_bgr, selfie_bgr)

    risk = risk_scorer.score(mrz_result, validation_result, tamper_result, face_result)

    extracted = {
        "valid_format": mrz_result.valid_format,
        "document_type": mrz_result.document_type,
        "issuing_country": mrz_result.issuing_country,
        "surname": mrz_result.surname,
        "given_names": mrz_result.given_names,
        "passport_number": mrz_result.passport_number,
        "nationality": mrz_result.nationality,
        "date_of_birth": mrz_result.date_of_birth,
        "sex": mrz_result.sex,
        "date_of_expiry": mrz_result.date_of_expiry,
        "checks": [c.__dict__ for c in mrz_result.checks],
        "errors": mrz_result.errors,
    }
    if merged_fields.get("merged_fields"):
        for k, v in merged_fields["merged_fields"].items():
            if v not in (None, ""):
                extracted[k] = v

    return {
        "ocr": ocr_result,
        "mrz": extracted,
        "visual_fields": merged_fields["visual_fields"],
        "document_fields": merged_fields["merged_fields"],
        "validation": validation_result,
        "tampering": tamper_result,
        "face_verification": face_result,
        "risk_assessment": risk,
    }
