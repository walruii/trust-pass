from datetime import datetime, timedelta, timezone
import base64
import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from typing import Literal
from sqlalchemy import exists, select, update
from sqlalchemy.orm import Session

from app.auth import create_access_token, verify_password, get_current_officer
from app.db.session import get_db
from app.models.application import Application
from app.models.user import User
from app.models.lease import ApplicationLease
from app.models.audit import ApplicationAuditEvent
from app.services.intake import create_application
from app.services.pipeline import process_application

router = APIRouter(prefix="/api/v1")
LEASE_DURATION = timedelta(minutes=10)


class KioskSubmitPayload(BaseModel):
    passport_base64: str = Field(min_length=1)
    selfie_base64: str = Field(min_length=1)
    kiosk_id: str = Field(min_length=1, max_length=100)


class KioskSubmitResponse(BaseModel):
    application_id: str
    status: str


class LoginPayload(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    officer_id: str
    display_name: str
    is_available: bool


class CurrentOfficerResponse(BaseModel):
    officer_id: str
    display_name: str
    role: str
    is_available: bool


class ApplicantStatusResponse(BaseModel):
    application_id: str
    status: str
    created_at: datetime
    completed_at: datetime | None = None
    decision_note: str | None = None


class ApplicationStatusResponse(ApplicantStatusResponse):
    kiosk_id: str
    pipeline_version: str
    attempt_count: int
    result_json: dict | None = None
    error_message: str | None = None


class OfficerApplicationResponse(ApplicationStatusResponse):
    passport_image: str | None = None
    selfie_image: str | None = None
    review_fields: dict
    assigned_officer_id: str | None = None
    lease_expires_at: datetime | None = None
    claim_token: str | None = None


class OfficerDecisionPayload(BaseModel):
    decision: Literal["APPROVED", "REJECTED_IMPROPER", "REJECTED_TAMPERING"]
    decision_note: str | None = Field(default=None, max_length=2000)


class OfficerDecisionResponse(BaseModel):
    application_id: str
    status: str


class OfficerAvailabilityPayload(BaseModel):
    available: bool


class OfficerAvailabilityResponse(BaseModel):
    officer_id: str
    available: bool


class NextApplicationResponse(BaseModel):
    available: bool
    application: OfficerApplicationResponse | None = None


class AuditEventResponse(BaseModel):
    event_type: str
    actor_id: str | None
    from_status: str | None
    to_status: str | None
    note: str | None
    details: dict | None
    created_at: datetime


@router.post("/auth/login", response_model=LoginResponse, tags=["Auth"])
async def login(payload: LoginPayload, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()

    if user is None or user.role != "OFFICER" or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    token = create_access_token({"sub": user.id, "role": user.role})
    return {
        "access_token": token,
        "token_type": "bearer",
        "officer_id": user.id,
        "display_name": user.display_name,
        "is_available": user.is_available,
    }


@router.get("/auth/me", response_model=CurrentOfficerResponse, tags=["Auth"])
async def current_officer(current_officer: dict = Depends(get_current_officer)):
    return current_officer


@router.post(
    "/officer/availability",
    response_model=OfficerAvailabilityResponse,
    tags=["Officer"],
)
async def set_officer_availability(
    payload: OfficerAvailabilityPayload,
    db: Session = Depends(get_db),
    current_officer: dict = Depends(get_current_officer),
):
    officer = db.get(User, current_officer["officer_id"])
    officer.is_available = payload.available
    db.add(
        ApplicationAuditEvent(
            actor_id=officer.id,
            event_type="AVAILABILITY_CHANGED",
            note="Officer became available" if payload.available else "Officer became unavailable",
            details={"available": payload.available},
        )
    )
    db.commit()
    return {"officer_id": officer.id, "available": officer.is_available}


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
    response_model=ApplicantStatusResponse,
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

    return ApplicantStatusResponse(
        application_id=application.id,
        status=application.status,
        created_at=application.created_at,
        completed_at=application.completed_at,
        decision_note=application.decision_note,
    )


@router.get(
    "/officer/applications",
    response_model=list[OfficerApplicationResponse],
    tags=["Officer"],
)
async def list_officer_applications(
    application_status: str = "PENDING_AUDIT",
    db: Session = Depends(get_db),
    current_officer: dict = Depends(get_current_officer),
):
    applications = db.scalars(
        select(Application)
        .where(Application.status == application_status.upper())
        .order_by(Application.created_at.asc())
    ).all()

    return [_officer_application_response(db, application, current_officer["officer_id"]) for application in applications]


@router.post(
    "/officer/applications/next",
    response_model=NextApplicationResponse,
    tags=["Officer"],
)
async def claim_next_application(
    db: Session = Depends(get_db),
    current_officer: dict = Depends(get_current_officer),
):
    now = datetime.now(timezone.utc)
    active_lease = ApplicationLease.released_at.is_(None)
    db.rollback()

    officer = db.get(User, current_officer["officer_id"])
    if officer is None or not officer.is_available:
        return {"available": False, "application": None}
    db.rollback()

    with db.begin():
        db.execute(
            update(ApplicationLease)
            .where(active_lease, ApplicationLease.lease_expires_at <= now)
            .values(released_at=now)
        )
        application = db.scalars(
            select(Application)
            .where(
                Application.status == "PENDING_AUDIT",
                ~exists(
                    select(ApplicationLease.id).where(
                        ApplicationLease.application_id == Application.id,
                        active_lease,
                    )
                ),
            )
            .order_by(Application.created_at.asc(), Application.id.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        ).first()

        if application is None:
            return {"available": False, "application": None}

        lease = ApplicationLease(
            application_id=application.id,
            officer_id=current_officer["officer_id"],
            claim_token=secrets.token_urlsafe(32),
            lease_expires_at=now + LEASE_DURATION,
        )
        db.add(lease)
        db.add(
            ApplicationAuditEvent(
                application_id=application.id,
                actor_id=current_officer["officer_id"],
                event_type="APPLICATION_CLAIMED",
                from_status=application.status,
                to_status=application.status,
                details={"lease_expires_at": lease.lease_expires_at.isoformat()},
            )
        )
        db.flush()

    return {
        "available": True,
        "application": _officer_application_response(
            db, application, current_officer["officer_id"], lease
        ),
    }


@router.get(
    "/officer/applications/{application_id}/audit",
    response_model=list[AuditEventResponse],
    tags=["Officer"],
)
async def get_application_audit(
    application_id: str,
    db: Session = Depends(get_db),
    current_officer: dict = Depends(get_current_officer),
):
    events = db.scalars(
        select(ApplicationAuditEvent)
        .where(ApplicationAuditEvent.application_id == application_id)
        .order_by(ApplicationAuditEvent.created_at.asc())
    ).all()
    return [
        {
            "event_type": event.event_type,
            "actor_id": event.actor_id,
            "from_status": event.from_status,
            "to_status": event.to_status,
            "note": event.note,
            "details": event.details,
            "created_at": event.created_at,
        }
        for event in events
    ]


@router.post(
    "/officer/applications/{application_id}/decision",
    response_model=OfficerDecisionResponse,
    tags=["Officer"],
)
async def decide_application(
    application_id: str,
    payload: OfficerDecisionPayload,
    db: Session = Depends(get_db),
    current_officer: dict = Depends(get_current_officer),
    claim_token: str = Header(..., alias="X-Claim-Token"),
):
    application = db.get(Application, application_id, with_for_update=True)

    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    if application.status != "PENDING_AUDIT":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only applications pending audit can receive a decision",
        )

    lease = _get_owned_lease(db, application_id, current_officer["officer_id"], claim_token)
    if lease is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Application is not actively claimed by this officer")

    application.status = payload.decision
    application.decision_note = payload.decision_note.strip() if payload.decision_note else None
    application.decision_by = current_officer["officer_id"]
    application.decision_at = datetime.now(timezone.utc)
    application.completed_at = datetime.now(timezone.utc)
    lease.released_at = application.decision_at
    db.add(
        ApplicationAuditEvent(
            application_id=application.id,
            actor_id=current_officer["officer_id"],
            event_type="APPLICATION_DECISION",
            from_status="PENDING_AUDIT",
            to_status=application.status,
            note=application.decision_note,
        )
    )
    db.commit()

    return {
        "application_id": application.id,
        "status": application.status,
    }


@router.post("/officer/applications/{application_id}/renew", tags=["Officer"])
async def renew_application_lease(
    application_id: str,
    db: Session = Depends(get_db),
    current_officer: dict = Depends(get_current_officer),
    claim_token: str = Header(..., alias="X-Claim-Token"),
):
    lease = _get_owned_lease(db, application_id, current_officer["officer_id"], claim_token)
    if lease is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Application lease is missing or expired")
    lease.lease_expires_at = datetime.now(timezone.utc) + LEASE_DURATION
    db.add(
        ApplicationAuditEvent(
            application_id=application_id,
            actor_id=current_officer["officer_id"],
            event_type="LEASE_RENEWED",
            details={"lease_expires_at": lease.lease_expires_at.isoformat()},
        )
    )
    db.commit()
    return {"application_id": application_id, "lease_expires_at": lease.lease_expires_at}


@router.post("/officer/applications/{application_id}/release", tags=["Officer"])
async def release_application_lease(
    application_id: str,
    db: Session = Depends(get_db),
    current_officer: dict = Depends(get_current_officer),
    claim_token: str = Header(..., alias="X-Claim-Token"),
):
    lease = _get_owned_lease(db, application_id, current_officer["officer_id"], claim_token)
    if lease is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Application lease is missing or expired")
    lease.released_at = datetime.now(timezone.utc)
    db.add(
        ApplicationAuditEvent(
            application_id=application_id,
            actor_id=current_officer["officer_id"],
            event_type="LEASE_RELEASED",
        )
    )
    db.commit()
    return {"application_id": application_id, "released": True}


def _get_owned_lease(
    db: Session,
    application_id: str,
    officer_id: str,
    claim_token: str,
) -> ApplicationLease | None:
    return db.scalars(
        select(ApplicationLease)
        .where(
            ApplicationLease.application_id == application_id,
            ApplicationLease.officer_id == officer_id,
            ApplicationLease.claim_token == claim_token,
            ApplicationLease.released_at.is_(None),
            ApplicationLease.lease_expires_at > datetime.now(timezone.utc),
        )
        .with_for_update()
    ).first()


def _officer_application_response(
    db: Session,
    application: Application,
    officer_id: str,
    lease: ApplicationLease | None = None,
) -> OfficerApplicationResponse:
    if lease is None:
        lease = db.scalars(
            select(ApplicationLease).where(
                ApplicationLease.application_id == application.id,
                ApplicationLease.released_at.is_(None),
                ApplicationLease.lease_expires_at > datetime.now(timezone.utc),
            )
        ).first()
    owns_lease = lease is not None and lease.officer_id == officer_id
    return OfficerApplicationResponse(
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
        assigned_officer_id=lease.officer_id if lease else None,
        lease_expires_at=lease.lease_expires_at if lease else None,
        claim_token=lease.claim_token if owns_lease else None,
    )


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

