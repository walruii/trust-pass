"""
Module 1: OCR Extraction.

Extracts raw text from the document image using Tesseract, with a
dedicated pass tuned for the MRZ band (fixed-width font, restricted
character set) plus a general pass for the visual (human-readable) zone.
"""
import re

import cv2
import numpy as np
import pytesseract
from pytesseract import Output

MRZ_WHITELIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"


def _preprocess(gray: np.ndarray) -> np.ndarray:
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    gray = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
    )
    return gray


def _normalize_spaces(value: str) -> str:
    if value is None:
        return ""
    value = value.upper().replace("\n", " ")
    value = re.sub(r"\s+", " ", value)
    value = value.strip(" -:;,.\t")
    return value


def _safe_regex_search(text: str, patterns):
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
    return ""


def _normalize_word(word: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (word or "").upper())


def _extract_fields_from_word_boxes(words):
    results = {"given_names": "", "surname": "", "passport_number": "", "nationality": "", "date_of_birth": "", "date_of_expiry": "", "sex": ""}
    anchor_map = {
        "given_names": ["GIVEN", "GIVENNAMES", "FIRSTNAME", "NAME"],
        "surname": ["SURNAME", "LASTNAME", "FAMILYNAME"],
        "passport_number": ["PASSPORT", "DOCNO", "NUMBER"],
        "nationality": ["NATIONALITY", "NAT"],
        "date_of_birth": ["DOB", "DATEOFBIRTH"],
        "date_of_expiry": ["EXPIRY", "VALIDUNTIL", "DATEOFEXPIRY"],
        "sex": ["SEX", "GENDER"],
    }

    for idx, item in enumerate(words):
        text = (item.get("text") or "").strip()
        norm = _normalize_word(text)
        for key, anchors in anchor_map.items():
            for anchor in anchors:
                if norm == _normalize_word(anchor):
                    values = []
                    for nxt in words[idx + 1:]:
                        nxt_text = (nxt.get("text") or "").strip()
                        if not nxt_text:
                            continue
                        nxt_norm = _normalize_word(nxt_text)
                        if nxt_norm in {"", "PASSPORT", "DOCNO", "NUMBER", "NATIONALITY", "NAT", "DOB", "EXPIRY", "SEX", "GENDER"}:
                            continue
                        if nxt.get("left", 0) <= item.get("left", 0) + 500:
                            values.append(nxt_text)
                            continue
                        break
                    if values:
                        val = " ".join(values).strip(" :;-./")
                        if val:
                            results[key] = val
                    break
            if results[key]:
                break

    # Keep only likely date/passport patterns.
    for key in ["passport_number", "nationality", "date_of_birth", "date_of_expiry", "sex"]:
        value = results.get(key, "")
        if key == "passport_number" and value:
            results[key] = re.sub(r"[^A-Z0-9<]", "", value.upper())
        elif key in {"nationality", "sex"}:
            results[key] = re.sub(r"[^A-Z]", "", value.upper())
        elif key in {"date_of_birth", "date_of_expiry"}:
            results[key] = re.sub(r"[^0-9/]", "", value)
    return results


def _extract_visual_fields_from_text(ocr_text: str, image: np.ndarray = None):
    text = (ocr_text or "").upper()
    text = text.replace("\r", "\n")

    fields = {
        "given_names": _safe_regex_search(text, [
            r"GIVEN\s+NAMES?\s*[:\-]?\s*([A-Z][A-Z\s'./-]+)",
            r"GIVEN\s+NAME\s*[:\-]?\s*([A-Z][A-Z\s'./-]+)",
            r"FIRST\s+NAME\s*[:\-]?\s*([A-Z][A-Z\s'./-]+)",
        ]),
        "surname": _safe_regex_search(text, [
            r"SURNAME\s*[:\-]?\s*([A-Z][A-Z\s'./-]+)",
            r"FAMILY\s+NAME\s*[:\-]?\s*([A-Z][A-Z\s'./-]+)",
            r"LAST\s+NAME\s*[:\-]?\s*([A-Z][A-Z\s'./-]+)",
        ]),
        "passport_number": _safe_regex_search(text, [
            r"PASSPORT\s*(?:NO|NUMBER)?\s*[:\-]?\s*([A-Z0-9<]+)",
            r"DOC\s*NO\.?\s*[:\-]?\s*([A-Z0-9<]+)",
            r"NUMBER\s*[:\-]?\s*([A-Z0-9<]+)",
        ]),
        "nationality": _safe_regex_search(text, [
            r"NATIONALITY\s*[:\-]?\s*([A-Z]{2,3})",
            r"NAT\.?\s*[:\-]?\s*([A-Z]{2,3})",
        ]),
        "date_of_birth": _safe_regex_search(text, [
            r"DATE\s+OF\s+BIRTH\s*[:\-]?\s*(\d{2}[/-]?\d{2}[/-]?\d{2,4})",
            r"DOB\s*[:\-]?\s*(\d{2}[/-]?\d{2}[/-]?\d{2,4})",
        ]),
        "date_of_expiry": _safe_regex_search(text, [
            r"DATE\s+OF\s+EXPIRY\s*[:\-]?\s*(\d{2}[/-]?\d{2}[/-]?\d{2,4})",
            r"EXPIRY\s*[:\-]?\s*(\d{2}[/-]?\d{2}[/-]?\d{2,4})",
            r"VALID\s+UNTIL\s*[:\-]?\s*(\d{2}[/-]?\d{2}[/-]?\d{2,4})",
        ]),
        "sex": _safe_regex_search(text, [
            r"SEX\s*[:\-]?\s*([MFX])",
            r"GENDER\s*[:\-]?\s*([MFX])",
        ]),
    }

    if image is not None:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = _preprocess(gray)
        ocr_data = pytesseract.image_to_data(gray, config="--psm 6", output_type=Output.DICT)
        words = []
        for i, word in enumerate(ocr_data.get("text", [])):
            if not word or not word.strip():
                continue
            words.append({
                "text": word,
                "left": int(ocr_data["left"][i]),
                "top": int(ocr_data["top"][i]),
                "width": int(ocr_data["width"][i]),
                "height": int(ocr_data["height"][i]),
            })
        box_fields = _extract_fields_from_word_boxes(words)
        for key, value in box_fields.items():
            if value:
                fields[key] = value

    for key, val in list(fields.items()):
        fields[key] = _normalize_spaces(val)
    if fields["passport_number"] and not re.fullmatch(r"[A-Z0-9<]+", fields["passport_number"], flags=re.I):
        fields["passport_number"] = ""
    return fields


def _canonicalize(value: str) -> str:
    if value is None:
        return ""
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def merge_mrz_and_visual(mrz_fields: dict, visual_fields: dict):
    merged = dict(mrz_fields or {})
    for key in ["given_names", "surname", "passport_number", "nationality", "date_of_birth", "date_of_expiry", "sex"]:
        mrz_value = (mrz_fields or {}).get(key, "")
        visual_value = (visual_fields or {}).get(key, "")
        if not visual_value:
            continue
        if not mrz_value:
            merged[key] = visual_value
            continue
        if _canonicalize(visual_value) == _canonicalize(mrz_value):
            merged[key] = mrz_value
            continue
        if key in {"given_names", "surname"}:
            if _canonicalize(mrz_value) in _canonicalize(visual_value) or _canonicalize(visual_value) in _canonicalize(mrz_value):
                merged[key] = mrz_value
                continue
        if key in {"date_of_birth", "date_of_expiry"}:
            if _canonicalize(mrz_value) in _canonicalize(visual_value) or _canonicalize(visual_value) in _canonicalize(mrz_value):
                merged[key] = mrz_value
                continue
        if key == "passport_number":
            if _canonicalize(mrz_value) in _canonicalize(visual_value) or _canonicalize(visual_value) in _canonicalize(mrz_value):
                merged[key] = mrz_value
                continue
        merged[key] = mrz_value
    return merged


# def extract_mrz_text(image_bgr: np.ndarray) -> str:
#     """Run OCR on the bottom ~25% of the image (where TD3 MRZ lives),
#     restricted to the MRZ character set for much cleaner output."""
#     h, w = image_bgr.shape[:2]
#     band = image_bgr[int(h * 0.70):h, 0:w]
#     gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
#     gray = _preprocess(gray)
#     config = f"--psm 6 -c tessedit_char_whitelist={MRZ_WHITELIST}"
#     text = pytesseract.image_to_string(gray, config=config)
#     return text

def extract_mrz_text(image_bgr: np.ndarray) -> str:
    """Run OCR on the bottom ~35% of the image with upscaling,
    padding, and thresholding tuned for MRZ text."""
    h, w = image_bgr.shape[:2]

    # 1. Expand crop to bottom 35% (int(h * 0.65)) to avoid cutting off top MRZ line
    band = image_bgr[int(h * 0.65):h, 0:w]

    # 2. Convert to grayscale
    gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)

    # 3. Upscale image 2x (Tesseract needs characters to be ~30-40px high)
    gray = cv2.resize(gray, (0, 0), fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

    # 4. Increase contrast via Otsu's thresholding
    # (Replaces generic _preprocess if it was over-smoothing or blurring)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 5. Add a 20px white border around the crop
    # Tesseract's page segmenter often skips text that touches the image boundary
    padded = cv2.copyMakeBorder(
        thresh, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=[255, 255, 255]
    )

    # 6. Tesseract Config
    # --psm 6 assumes a single uniform block of text
    config = f"--psm 6 -c tessedit_char_whitelist={MRZ_WHITELIST}"

    # Execute OCR
    text = pytesseract.image_to_string(padded, config=config)
    return text.strip()


def extract_visual_text(image_bgr: np.ndarray) -> str:
    h, w = image_bgr.shape[:2]
    top = image_bgr[:int(h * 0.6), 0:w]
    gray = cv2.cvtColor(top, cv2.COLOR_BGR2GRAY)
    gray = _preprocess(gray)
    return pytesseract.image_to_string(gray, config="--psm 6")


def extract_full_text(image_bgr: np.ndarray) -> str:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    gray = _preprocess(gray)
    return pytesseract.image_to_string(gray, config="--psm 4")


def extract_document_fields(image_bgr: np.ndarray, mrz_result=None):
    visual_text = extract_visual_text(image_bgr)
    visual_fields = _extract_visual_fields_from_text(visual_text, image_bgr)

    if mrz_result is None:
        return {
            "visual_text": visual_text,
            "visual_fields": visual_fields,
            "merged_fields": visual_fields,
        }

    mrz_fields = {
        "given_names": mrz_result.given_names,
        "surname": mrz_result.surname,
        "passport_number": mrz_result.passport_number,
        "nationality": mrz_result.nationality,
        "date_of_birth": mrz_result.date_of_birth,
        "date_of_expiry": mrz_result.date_of_expiry,
        "sex": mrz_result.sex,
    }
    merged = merge_mrz_and_visual(mrz_fields, visual_fields)

    return {
        "visual_text": visual_text,
        "visual_fields": visual_fields,
        "merged_fields": merged,
    }


def extract_all(image_bgr: np.ndarray) -> dict:
    return {
        "mrz_text": extract_mrz_text(image_bgr),
        "visual_zone_text": extract_full_text(image_bgr),
        "visual_text_top": extract_visual_text(image_bgr),
    }
