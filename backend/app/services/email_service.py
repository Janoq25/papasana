"""Envío de correos en segundo plano (Celery). En desarrollo, Mailpit los captura."""

import logging

log = logging.getLogger("papasana")


def enqueue_email(to: str, subject: str, body: str) -> None:
    from app.workers.tasks import send_email

    try:
        send_email.delay(to, subject, body)
    except Exception:  # el broker no disponible no debe romper el flujo de la petición
        log.exception("No se pudo encolar el correo para %s", to)


def password_reset_email(full_name: str, link: str, minutes: int) -> tuple[str, str]:
    subject = "PapaSana AP-01 · Restablecer contraseña"
    body = (
        f"Hola {full_name}:\n\n"
        "Recibimos una solicitud para restablecer su contraseña. Use el siguiente enlace "
        f"(válido por {minutes} minutos):\n\n{link}\n\n"
        "Si usted no hizo esta solicitud, ignore este mensaje; su contraseña no cambiará.\n\n"
        "— PapaSana AP-01"
    )
    return subject, body
