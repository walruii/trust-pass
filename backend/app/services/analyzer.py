import os
import tempfile
from typing import Any

import cv2
import numpy as np

from app.services import document_ocr, face_module, mrz, risk_scorer, tamper_detection, validation


ANALYZER_VERSION = "1.0"


def analyze_document_images(
    passport_bytes: bytes | None,
    passport_mime_type: str | None,
    selfie_bytes: bytes | None,
    selfie_mime_type: str | None,
) -> dict[str, Any]:
    result = _empty_result()
    passport_image = _decode_image(passport_bytes)
    selfie_image = _decode_image(selfie_bytes)

    result["input"] = {
        "passport": _image_metadata(passport_image, passport_mime_type),
        "selfie": _image_metadata(selfie_image, selfie_mime_type),
    }

    if passport_image is None:
        result["ocr"] = _stage("not_detected", "Passport image could not be decoded")
        result["errors"].append("Passport image is missing or unreadable")
        return result

    ocr_result = _run_ocr(passport_image, result)
    mrz_result = mrz.parse_td3_mrz(ocr_result["mrz_text"])
    merged_fields = document_ocr.extract_document_fields(passport_image, mrz_result)
    validation_result = validation.validate_fields(mrz_result)

    result["ocr"] = {
        "status": "passed" if mrz_result.valid_format else "not_detected",
        **ocr_result,
        "fields": _legacy_fields(mrz_result, merged_fields["merged_fields"]),
    }
    result["mrz"] = _serialize_mrz(mrz_result)
    result["document_fields"] = merged_fields["merged_fields"]
    result["visual_fields"] = merged_fields["visual_fields"]
    result["validation"] = {
        "status": "passed" if not validation_result["issues"] else "flagged",
        **validation_result,
    }

    result["tampering"] = _run_tampering(passport_image, result)
    result["face_verification"] = _run_face_check(passport_image, selfie_image, result)
    result["risk_assessment"] = _run_risk(
        mrz_result,
        validation_result,
        result["tampering"],
        result["face_verification"],
        result,
    )
    return result


def _empty_result() -> dict[str, Any]:
    return {
        "analyzer_version": ANALYZER_VERSION,
        "status": "completed",
        "input": {},
        "ocr": _stage("not_run"),
        "mrz": {"status": "not_run", "fields": {}, "checks": [], "errors": []},
        "document_fields": {},
        "visual_fields": {},
        "validation": _stage("not_run", issues=[], info={}),
        "tampering": _stage("not_run"),
        "face_verification": _stage("not_run"),
        "risk_assessment": _stage("not_run"),
        "errors": [],
    }


def _stage(status: str, message: str | None = None, **values: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"status": status}
    if message is not None:
        result["message"] = message
    result.update(values)
    return result


def _decode_image(image_bytes: bytes | None) -> np.ndarray | None:
    if not image_bytes:
        return None
    buffer = np.frombuffer(image_bytes, dtype=np.uint8)
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR)


def _image_metadata(image: np.ndarray | None, mime_type: str | None) -> dict[str, Any]:
    if image is None:
        return {"status": "not_detected", "mime_type": mime_type, "width": None, "height": None}
    height, width = image.shape[:2]
    return {
        "status": "passed",
        "mime_type": mime_type,
        "width": width,
        "height": height,
        "channels": image.shape[2] if image.ndim == 3 else 1,
    }


def _run_ocr(image: np.ndarray, result: dict[str, Any]) -> dict[str, Any]:
    try:
        return document_ocr.extract_all(image)
    except Exception as error:
        result["errors"].append(f"OCR failed: {error}")
        return {"mrz_text": "", "visual_zone_text": "", "visual_text_top": ""}


def _legacy_fields(mrz_result: mrz.MRZResult, merged_fields: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": mrz_result.surname or merged_fields.get("surname") or None,
        "surname": mrz_result.surname or merged_fields.get("surname") or None,
        "given_names": mrz_result.given_names or merged_fields.get("given_names") or None,
        "date_of_birth": mrz_result.date_of_birth or merged_fields.get("date_of_birth") or None,
        "expiry": mrz_result.date_of_expiry or merged_fields.get("date_of_expiry") or None,
        "date_of_expiry": mrz_result.date_of_expiry or merged_fields.get("date_of_expiry") or None,
        "passport_number": mrz_result.passport_number or merged_fields.get("passport_number") or None,
        "nationality": mrz_result.nationality or merged_fields.get("nationality") or None,
        "issuing_country": mrz_result.issuing_country or None,
        "sex": mrz_result.sex or merged_fields.get("sex") or None,
    }


def _serialize_mrz(mrz_result: mrz.MRZResult) -> dict[str, Any]:
    fields = {
        key: getattr(mrz_result, key)
        for key in (
            "document_type",
            "issuing_country",
            "surname",
            "given_names",
            "passport_number",
            "nationality",
            "date_of_birth",
            "sex",
            "date_of_expiry",
        )
    }
    return {
        "status": "passed" if mrz_result.valid_format else "not_detected",
        "valid_format": mrz_result.valid_format,
        "fields": fields,
        "checks": [check.__dict__ for check in mrz_result.checks],
        "errors": mrz_result.errors,
    }


def _run_tampering(image: np.ndarray, result: dict[str, Any]) -> dict[str, Any]:
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as image_file:
            temporary_path = image_file.name
        if not cv2.imwrite(temporary_path, image):
            raise RuntimeError("Could not write temporary image")
        tampering = tamper_detection.run_all(image, temporary_path)
        flagged = bool(
            tampering.get("error_level_analysis", {}).get("suspicious_regions")
            or tampering.get("copy_move", {}).get("duplicated_regions_found")
            or tampering.get("metadata", {}).get("flags")
        )
        return {"status": "flagged" if flagged else "passed", **tampering}
    except Exception as error:
        result["errors"].append(f"Tamper analysis failed: {error}")
        return _stage("failed", str(error))
    finally:
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass


def _run_face_check(
    passport_image: np.ndarray,
    selfie_image: np.ndarray | None,
    result: dict[str, Any],
) -> dict[str, Any]:
    if selfie_image is None:
        return _stage("not_run", "Selfie image is missing")
    try:
        face_result = face_module.compare_faces(passport_image, selfie_image)
        status = "passed" if face_result.get("match") else "flagged"
        if face_result.get("similarity") is None:
            status = "not_detected"
        return {"status": status, **face_result}
    except Exception as error:
        result["errors"].append(f"Face verification failed: {error}")
        return _stage("failed", str(error))


def _run_risk(mrz_result, validation_result, tampering, face_result, result):
    try:
        risk = risk_scorer.score(mrz_result, validation_result, tampering, face_result)
        return {"status": "flagged" if risk["fake_probability_percent"] >= 20 else "passed", **risk}
    except Exception as error:
        result["errors"].append(f"Risk assessment failed: {error}")
        return _stage("failed", str(error))
