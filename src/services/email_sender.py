import json
import smtplib
import time
from email.message import EmailMessage
from pathlib import Path
from datetime import datetime, timezone


class EmailSender:
    def __init__(self, mode, outbox_dir, sender, smtp: dict, smtp_factory=None):
        self.mode = mode
        self.outbox_dir = outbox_dir
        self.sender = sender
        self.smtp = smtp
        self.smtp_factory = smtp_factory or smtplib.SMTP

    def send(self, to, subject, text, html, attachments=None) -> str:
        message_id = str(time.time())
        
        if self.mode == "outbox":
            return self._send_outbox(to, subject, text, html, attachments, message_id)
        elif self.mode == "smtp":
            return self._send_smtp(to, subject, text, html, attachments, message_id)
        else:
            raise ValueError(f"Unknown mode: {self.mode}")

    def _send_outbox(self, to, subject, text, html, attachments, message_id):
        # Ensure outbox directory exists
        Path(self.outbox_dir).mkdir(parents=True, exist_ok=True)
        
        # Create message data
        message_data = {
            "id": message_id,
            "to": to,
            "from": self.sender,
            "subject": subject,
            "text": text,
            "html": html,
            "attachments": [
                {
                    "filename": attachment[0],
                    "mime_type": attachment[2],
                    "size": len(attachment[1])
                }
                for attachment in (attachments or [])
            ],
            "sent_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Write to JSON file
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        filename = f"{timestamp}-{message_id}.json"
        file_path = Path(self.outbox_dir) / filename
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(message_data, f, ensure_ascii=False, indent=2)
        
        return message_id

    def _send_smtp(self, to, subject, text, html, attachments, message_id):
        # Create email message
        msg = EmailMessage()
        msg["From"] = self.sender
        msg["To"] = to
        msg["Subject"] = subject
        
        # Add text and HTML parts
        msg.set_content(text)
        msg.add_alternative(html, subtype="html")
        
        # Add attachments
        if attachments:
            for filename, content, mime_type in attachments:
                msg.add_attachment(
                    content,
                    maintype="application",
                    subtype=mime_type.split("/")[1] if "/" in mime_type else "octet-stream",
                    filename=filename
                )
        
        # Connect to SMTP server
        smtp_client = self.smtp_factory(
            self.smtp.get("host", "localhost"),
            self.smtp.get("port", 587)
        )
        
        try:
            # Start TLS if configured
            if self.smtp.get("starttls", False):
                smtp_client.starttls()
            
            # Login if credentials provided
            user = self.smtp.get("user")
            password = self.smtp.get("password")
            if user and password:
                smtp_client.login(user, password)
            
            # Send message
            smtp_client.send_message(msg)
        finally:
            # Always quit the connection
            smtp_client.quit()
        
        return message_id