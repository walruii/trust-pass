from datetime import datetime, timezone

from sqlalchemy import update

from app.db.session import SessionLocal
from app.models.audit import ApplicationAuditEvent
from app.models.application import Application
from app.services.ocr import extract_passport_data


PIPELINE_VERSION = "1.0"


def run_placeholder_stages(application: Application) -> dict:
    passport_image = next(
        (image for image in application.images if image.image_type == "passport"),
        None,
    )
    ocr_result = (
        extract_passport_data(passport_image.image_bytes, passport_image.mime_type)
        if passport_image is not None
        else {
            "status": "MISSING_INPUT",
            "provider": "none",
            "fields": {},
            "mrz": None,
            "message": "Passport image is missing",
        }
    )

    return {
        "ocr": ocr_result,
        "document_validation": {"status": "PENDING_IMPLEMENTATION"},
        "anti_tampering": {"status": "PENDING_IMPLEMENTATION"},
        "passport_photo_extraction": {"status": "PENDING_IMPLEMENTATION"},
        "face_comparison": {"status": "PENDING_IMPLEMENTATION"},
        "liveness": {"status": "PENDING_IMPLEMENTATION"},
        "input": {
            "image_count": len(application.images),
            "image_types": sorted(image.image_type for image in application.images),
        },
    }


def process_application(application_id: str) -> None:
    db = SessionLocal()

    try:
        started_at = datetime.now(timezone.utc)
        claim_result = db.execute(
            update(Application)
            .where(
                Application.id == application_id,
                Application.status == "QUEUED",
            )
            .values(
                status="PROCESSING",
                pipeline_version=PIPELINE_VERSION,
                attempt_count=Application.attempt_count + 1,
                processing_started_at=started_at,
            )
        )
        if claim_result.rowcount != 1:
            db.rollback()
            return

        application = db.get(Application, application_id)
        if application is None:
            db.rollback()
            return

        db.add(
            ApplicationAuditEvent(
                application_id=application.id,
                event_type="PIPELINE_STARTED",
                from_status="QUEUED",
                to_status="PROCESSING",
                details={"pipeline_version": PIPELINE_VERSION},
            )
        )
        db.commit()

        application = db.get(Application, application_id)
        if application is None:
            return

        application.result_json = run_placeholder_stages(application)
        application.status = "PENDING_AUDIT"
        application.completed_at = datetime.now(timezone.utc)
        db.add(
            ApplicationAuditEvent(
                application_id=application.id,
                event_type="PIPELINE_COMPLETED",
                from_status="PROCESSING",
                to_status="PENDING_AUDIT",
            )
        )
        db.commit()
    except Exception as error:
        db.rollback()
        application = db.get(Application, application_id)
        if application is not None:
            previous_status = application.status
            application.status = "FAILED"
            application.error_message = str(error)
            db.add(
                ApplicationAuditEvent(
                    application_id=application.id,
                    event_type="PIPELINE_FAILED",
                    from_status=previous_status,
                    to_status="FAILED",
                    note=str(error),
                )
            )
            db.commit()
    finally:
        db.close()
