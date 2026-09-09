from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
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

