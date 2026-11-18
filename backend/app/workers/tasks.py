import logging
import smtplib
import uuid
from email.message import EmailMessage

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError
from app.workers.celery_app import celery_app

log = logging.getLogger("papasana")


@celery_app.task(name="correo.enviar", autoretry_for=(OSError, smtplib.SMTPException), retry_backoff=True,
                 max_retries=5)
def send_email(to: str, subject: str, body: str) -> None:
    s = get_settings()
    msg = EmailMessage()
    msg["From"] = s.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
        smtp.send_message(msg)


@celery_app.task(name="diagnostico.procesar_imagen", bind=True, max_retries=3, default_retry_delay=20)
def process_image(self, image_id: str) -> str | None:
    """Inferencia de una imagen de un lote (se reintenta si ml-service no está disponible)."""
    from app.db.session import SessionLocal
    from app.services.diagnosis_service import DiagnosisService
    from app.services.ml_client import get_ml_client
    from app.services.storage_service import get_storage

    with SessionLocal() as db:
        svc = DiagnosisService(db, get_storage(), get_ml_client())
        try:
            final = self.request.retries >= self.max_retries
            diag = svc.process_batch_image(uuid.UUID(image_id), count_failure=final)
        except ServiceUnavailableError as e:
            if self.request.retries < self.max_retries:
                raise self.retry(exc=e) from e
            log.error("No se pudo procesar la imagen %s tras %s intentos", image_id, self.max_retries)
            return None
        return str(diag.id) if diag else None


@celery_app.task(name="reportes.generar", bind=True, max_retries=2, default_retry_delay=15)
def generate_report(self, job_id: str) -> str | None:
    """Genera un reporte solicitado y lo guarda en MinIO (los errores quedan registrados en el propio job)."""
    from app.db.session import SessionLocal
    from app.services.report_service import ReportService
    from app.services.storage_service import get_storage

    with SessionLocal() as db:
        job = ReportService(db, get_storage()).run(uuid.UUID(job_id))
        return job.status if job else None
