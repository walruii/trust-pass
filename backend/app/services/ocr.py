from dataclasses import dataclass
import importlib.util
import os
import shutil
import tempfile
from typing import Protocol


@dataclass
class OcrResult:
    status: str
    provider: str
    fields: dict[str, str | None]
    mrz: str | None = None
    message: str | None = None
    validation: dict | None = None
    flags: list[str] | None = None


class PassportOcrProvider(Protocol):
    def extract(self, image_bytes: bytes, mime_type: str) -> OcrResult:
        ...


def get_ocr_runtime_status() -> dict[str, object]:
    """Report installed OCR dependencies without loading model weights."""
    tesseract_path = shutil.which("tesseract")
    return {
        "passporteye_installed": importlib.util.find_spec("passporteye") is not None,
        "mrz_installed": importlib.util.find_spec("mrz") is not None,
        "easyocr_installed": importlib.util.find_spec("easyocr") is not None,
        "opencv_installed": importlib.util.find_spec("cv2") is not None,
        "numpy_installed": importlib.util.find_spec("numpy") is not None,
        "tesseract_available": tesseract_path is not None,
        "tesseract_path": tesseract_path,
    }


class UnconfiguredPassportOcr:
    """Explicit fallback until a real OCR provider is configured."""

    def extract(self, image_bytes: bytes, mime_type: str) -> OcrResult:
        return OcrResult(
            status="NOT_CONFIGURED",
            provider="none",
            fields={
                "name": None,
                "date_of_birth": None,
                "expiry": None,
                "passport_number": None,
            },
            message="No passport OCR provider is configured",
        )


class PassportEyeOcr:
    """Extract and validate a passport TD3 MRZ with PassportEye and mrz."""

    def extract(self, image_bytes: bytes, mime_type: str) -> OcrResult:
        from passporteye import read_mrz
        from mrz.checker.td3 import TD3CodeChecker

        suffix = ".png" if mime_type == "image/png" else ".jpg"
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as image_file:
                image_file.write(image_bytes)
                temporary_path = image_file.name

            parsed = read_mrz(temporary_path)
            if parsed is None:
                return OcrResult(
                    status="NOT_DETECTED",
                    provider="passporteye",
                    fields=_empty_fields(),
                    message="PassportEye did not detect an MRZ",
                    flags=["MRZ_NOT_DETECTED"],
                )

            parsed_fields = parsed.to_dict()
            mrz_code = _normalize_mrz(parsed_fields.get("mrz_code"))
            if not mrz_code:
                return OcrResult(
                    status="NOT_DETECTED",
                    provider="passporteye",
                    fields=_empty_fields(),
                    message="PassportEye returned no MRZ code",
                    flags=["MRZ_NOT_DETECTED"],
                )

            checker = TD3CodeChecker(mrz_code, compute_warnings=True)
            fields = checker.fields()
            flags: list[str] = []
            if not checker.result:
                flags.append("MRZ_INVALID")
            if fields.country != "IND":
                flags.append("COUNTRY_MISMATCH")
            if fields.nationality != "IND":
                flags.append("NATIONALITY_MISMATCH")

            return OcrResult(
                status="VALIDATED" if not flags else "FLAGGED",
                provider="passporteye",
                fields={
                    "name": fields.name,
                    "surname": fields.surname,
                    "date_of_birth": fields.birth_date,
                    "expiry": fields.expiry_date,
                    "passport_number": fields.document_number,
                    "nationality": fields.nationality,
                    "issuing_country": fields.country,
                },
                mrz=mrz_code,
                validation={
                    "valid": bool(checker.result),
                    "document_type": fields.document_type,
                    "check_digits": {
                        "birth_date": fields.birth_date_hash,
                        "expiry": fields.expiry_date_hash,
                        "document_number": fields.document_number_hash,
                        "composite": fields.final_hash,
                    },
                },
                flags=flags,
            )
        except Exception as error:
            return OcrResult(
                status="ERROR",
                provider="passporteye",
                fields=_empty_fields(),
                message=str(error),
                flags=["OCR_PROVIDER_ERROR"],
            )
        finally:
            if temporary_path:
                try:
                    os.unlink(temporary_path)
                except FileNotFoundError:
                    pass


def _empty_fields() -> dict[str, str | None]:
    return {
        "name": None,
        "surname": None,
        "date_of_birth": None,
        "expiry": None,
        "passport_number": None,
        "nationality": None,
        "issuing_country": None,
    }


def _normalize_mrz(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    lines = [line.strip().upper() for line in value.splitlines() if line.strip()]
    return "\n".join(lines) if len(lines) == 2 else None


def extract_passport_data(image_bytes: bytes, mime_type: str) -> dict:
    result = PassportEyeOcr().extract(image_bytes, mime_type)
    return {
        "status": result.status,
        "provider": result.provider,
        "fields": result.fields,
        "mrz": result.mrz,
        "message": result.message,
        "validation": result.validation,
        "flags": result.flags or [],
    }
