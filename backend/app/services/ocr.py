from dataclasses import dataclass
from typing import Protocol


@dataclass
class OcrResult:
    status: str
    provider: str
    fields: dict[str, str | None]
    mrz: str | None = None
    message: str | None = None


class PassportOcrProvider(Protocol):
    def extract(self, image_bytes: bytes, mime_type: str) -> OcrResult:
        ...


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


def extract_passport_data(image_bytes: bytes, mime_type: str) -> dict:
    result = UnconfiguredPassportOcr().extract(image_bytes, mime_type)
    return {
        "status": result.status,
        "provider": result.provider,
        "fields": result.fields,
        "mrz": result.mrz,
        "message": result.message,
    }
