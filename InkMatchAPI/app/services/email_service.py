from email.message import EmailMessage
import smtplib

from app.core.config import settings


class EmailServiceError(Exception):
    pass


def _smtp_ready() -> bool:
    return bool(
        settings.smtp_host
        and settings.smtp_username
        and settings.smtp_password
        and settings.smtp_from_email
    )


def send_email(subject: str, body: str, recipient: str) -> None:
    if not _smtp_ready():
        raise EmailServiceError('SMTP is not configured')

    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = f'{settings.smtp_from_name} <{settings.smtp_from_email}>'
    message['To'] = recipient
    message.set_content(body)

    try:
        if settings.smtp_use_tls:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
                smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(message)
    except Exception as exc:
        raise EmailServiceError(f'Failed to send email: {exc}') from exc


def send_verification_email(recipient: str, code: str) -> None:
    send_email(
        'InkMatch - подтверждение регистрации',
        (
            'Здравствуйте!\n\n'
            f'Ваш код подтверждения: {code}\n\n'
            'Введите его в приложении InkMatch, чтобы подтвердить email.\n'
            'Если вы не регистрировались, просто проигнорируйте это письмо.\n'
        ),
        recipient,
    )

