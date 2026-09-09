from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.models.application import Application


PIPELINE_VERSION = "1.0"


def run_placeholder_stages(application: Application) -> dict:
    return {
        "ocr": {"status": "PENDING_IMPLEMENTATION"},
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
        application = db.get(Application, application_id)
        if application is None or application.status != "QUEUED":
            return

        application.status = "PROCESSING"
        application.pipeline_version = PIPELINE_VERSION
        application.attempt_count += 1
        application.processing_started_at = datetime.now(timezone.utc)
        db.commit()

        application = db.get(Application, application_id)
        if application is None:
            return

        application.result_json = run_placeholder_stages(application)
        application.status = "PENDING_AUDIT"
        application.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as error:
        db.rollback()
        application = db.get(Application, application_id)
        if application is not None:
            application.status = "FAILED"
            application.error_message = str(error)
            db.commit()
    finally:
        db.close()
