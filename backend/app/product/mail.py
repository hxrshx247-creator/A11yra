import os
import smtplib
import ssl
from email.message import EmailMessage


class Mailer:
    def __init__(self, environment: str):
        self.host = os.getenv("SMTP_HOST")
        self.sender = os.getenv("SMTP_FROM")
        if environment != "dev" and not (self.host and self.sender):
            raise RuntimeError("Set SMTP_HOST and SMTP_FROM outside development.")

    def send(self, recipient: str, subject: str, content: str):
        if not self.host:
            print(f"[development mail] To: {recipient}\n{subject}\n{content}", flush=True)
            return
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(content)
        with smtplib.SMTP(self.host, int(os.getenv("SMTP_PORT", "587")), timeout=10) as client:
            client.starttls(context=ssl.create_default_context())
            if username := os.getenv("SMTP_USER"):
                client.login(username, os.environ["SMTP_PASSWORD"])
            client.send_message(message)
