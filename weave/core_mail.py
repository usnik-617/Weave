from __future__ import annotations

import smtplib
from email.message import EmailMessage

from weave import core


def send_email(to_email, subject, body):
    if not core.SMTP_HOST or not to_email:
        return False
    try:
        message = EmailMessage()
        message["From"] = core.SMTP_FROM
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)

        with smtplib.SMTP(core.SMTP_HOST, core.SMTP_PORT, timeout=10) as server:
            if core.SMTP_TLS:
                server.starttls()
            if core.SMTP_USER:
                server.login(core.SMTP_USER, core.SMTP_PASSWORD)
            server.send_message(message)
        return True
    except Exception as exc:
        core.logger.error(f"email_send_failed: {exc}")
        return False
