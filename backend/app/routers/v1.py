from datetime import datetime
import base64

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.application import Application
from app.services.intake import create_application
from app.services.pipeline import process_application

router = APIRouter(prefix="/api/v1")


class KioskSubmitPayload(BaseModel):
    passport_base64: str = Field(min_length=1)
    selfie_base64: str = Field(min_length=1)
    kiosk_id: str = Field(min_length=1, max_length=100)


class KioskSubmitResponse(BaseModel):
    application_id: str
    status: str


class ApplicationStatusResponse(BaseModel):
    application_id: str
    kiosk_id: str
    status: str
    pipeline_version: str
    attempt_count: int
    created_at: datetime
    result_json: dict | None = None
    error_message: str | None = None


class OfficerApplicationResponse(ApplicationStatusResponse):
    passport_image: str | None = None
    selfie_image: str | None = None
    review_fields: dict


@router.post(
    "/kiosk/submit",
    response_model=KioskSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Kiosk"],
)
async def kiosk_submit(
    payload: KioskSubmitPayload,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    application = create_application(
        db=db,
        kiosk_id=payload.kiosk_id,
        passport_data_url=payload.passport_base64,
        selfie_data_url=payload.selfie_base64,
    )
    background_tasks.add_task(process_application, application.id)
    return {
        "application_id": application.id,
        "status": application.status,
    }


@router.get(
    "/kiosk/applications/{application_id}",
    response_model=ApplicationStatusResponse,
    tags=["Kiosk"],
)
async def get_application_status(
    application_id: str,
    db: Session = Depends(get_db),
):
    application = db.get(Application, application_id)

    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    return ApplicationStatusResponse(
        application_id=application.id,
        kiosk_id=application.kiosk_id,
        status=application.status,
        pipeline_version=application.pipeline_version,
        attempt_count=application.attempt_count,
        created_at=application.created_at,
        result_json=application.result_json,
        error_message=application.error_message,
    )


@router.get(
    "/officer/applications",
    response_model=list[OfficerApplicationResponse],
    tags=["Officer"],
)
async def list_officer_applications(
    application_status: str = "PENDING_AUDIT",
    db: Session = Depends(get_db),
):
    applications = db.scalars(
        select(Application)
        .where(Application.status == application_status.upper())
        .order_by(Application.created_at.asc())
    ).all()

    return [
        OfficerApplicationResponse(
            application_id=application.id,
            kiosk_id=application.kiosk_id,
            status=application.status,
            pipeline_version=application.pipeline_version,
            attempt_count=application.attempt_count,
            created_at=application.created_at,
            result_json=application.result_json,
            error_message=application.error_message,
            passport_image=_image_data_url(application, "passport"),
            selfie_image=_image_data_url(application, "selfie"),
            review_fields=_review_fields(application),
        )
        for application in applications
    ]


def _image_data_url(application: Application, image_type: str) -> str | None:
    image = next(
        (stored_image for stored_image in application.images if stored_image.image_type == image_type),
        None,
    )
    if image is None:
        return None

    encoded_image = base64.b64encode(image.image_bytes).decode("ascii")
    return f"data:{image.mime_type};base64,{encoded_image}"


def _review_fields(application: Application) -> dict:
    return {
        "date_of_birth": {"value": "Not implemented", "matched": None},
        "name": {"value": "Not implemented", "matched": None},
        "expiry": {"value": "Not implemented", "matched": None},
        "passport_number": {"value": "Not implemented", "matched": None},
        "passport_exists_in_national_repository": {"value": "Not implemented", "matched": None},
        "face_match_score": {"value": None, "matched": None},
        "passport_anti_tamper_score": {"value": None, "matched": None},
    }

