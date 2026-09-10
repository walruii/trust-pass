from datetime import datetime, timezone

from sqlalchemy import update

from app.db.session import SessionLocal
from app.models.audit import ApplicationAuditEvent
from app.models.application import Application
from app.services.analyzer import analyze_document_images


PIPELINE_VERSION = "1.1"


def run_placeholder_stages(application: Application) -> dict:
    passport_image = next((image for image in application.images if image.image_type == "passport"), None)
    selfie_image = next((image for image in application.images if image.image_type == "selfie"), None)
    return analyze_document_images(
        passport_bytes=passport_image.image_bytes if passport_image else None,
        passport_mime_type=passport_image.mime_type if passport_image else None,
        selfie_bytes=selfie_image.image_bytes if selfie_image else None,
        selfie_mime_type=selfie_image.mime_type if selfie_image else None,
    )


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
