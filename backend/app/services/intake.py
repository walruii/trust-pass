import base64
import binascii
import hashlib
import re
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.application import Application, ApplicationImage

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_IMAGE_BYTES = 20 * 1024 * 1024
DATA_URL_PATTERN = re.compile(r"^data:(image/(?:jpeg|png));base64,(.+)$", re.IGNORECASE | re.DOTALL)


@dataclass
class DecodedImage:
    mime_type: str
    image_bytes: bytes
    sha256: str


def decode_image(data_url: str) -> DecodedImage:
    match = DATA_URL_PATTERN.fullmatch(data_url.strip())
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Image must be a JPEG or PNG Base64 data URL",
        )

    mime_type = match.group(1).lower()
    encoded_image = match.group(2)

    try:
        image_bytes = base64.b64decode(encoded_image, validate=True)
    except (ValueError, binascii.Error) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Image contains invalid Base64 data",
        ) from error

    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Image cannot be empty",
        )

    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Each image must be smaller than {MAX_IMAGE_BYTES // (1024 * 1024)} MB",
        )

    return DecodedImage(
        mime_type=mime_type,
        image_bytes=image_bytes,
        sha256=hashlib.sha256(image_bytes).hexdigest(),
    )


def create_application(
    db: Session,
    kiosk_id: str,
    passport_data_url: str,
    selfie_data_url: str,
) -> Application:
    if not kiosk_id.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="kiosk_id cannot be empty",
        )

    passport = decode_image(passport_data_url)
    selfie = decode_image(selfie_data_url)

    if len(passport.image_bytes) + len(selfie.image_bytes) > MAX_TOTAL_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="The combined image size is too large",
        )

    application = Application(kiosk_id=kiosk_id.strip(), status="QUEUED")
    application.images = [
        ApplicationImage(
            image_type="passport",
            mime_type=passport.mime_type,
            image_bytes=passport.image_bytes,
            byte_size=len(passport.image_bytes),
            sha256=passport.sha256,
        ),
        ApplicationImage(
            image_type="selfie",
            mime_type=selfie.mime_type,
            image_bytes=selfie.image_bytes,
            byte_size=len(selfie.image_bytes),
            sha256=selfie.sha256,
        ),
    ]

    try:
        db.add(application)
        db.commit()
        db.refresh(application)
    except Exception:
        db.rollback()
        raise

    return application
