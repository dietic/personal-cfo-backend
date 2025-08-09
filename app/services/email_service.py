from typing import Optional
import resend
from app.core.config import settings

class EmailService:
    def __init__(self):
        resend.api_key = settings.RESEND_API_KEY
        self.sender = getattr(settings, "EMAIL_FROM", "PersonalCFO <noreply@example.com>")

    def send_otp(self, to: str, code: str) -> bool:
        subject = "Verify your PersonalCFO account"
        html = f"""
        <div style='font-family: Inter, Arial, sans-serif; line-height:1.6;'>
            <h2>Verify your email</h2>
            <p>Use the following one-time code to verify your PersonalCFO account:</p>
            <div style='font-size:28px;font-weight:700;letter-spacing:6px;margin:16px 0;color:#111827'>{code}</div>
            <p>This code will expire in 10 minutes.</p>
            <p>If you didn't request this, you can ignore this email.</p>
        </div>
        """
        try:
            resend.Emails.send({
                "from": self.sender,
                "to": [to],
                "subject": subject,
                "html": html,
            })
            return True
        except Exception as e:
            # Log in real app
            print("Email send failed:", e)
            return False
