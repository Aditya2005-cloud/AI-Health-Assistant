"""
g_mail_user/__init__.py
-----------------------
Gmail Email Service Package for AI Health Assistant.

This is the CANONICAL package folder (Python requires underscores, not hyphens).
The old 'g-mail-user' folder has been merged here.

Exposes the single top-level function the rest of the app needs:

    from g_mail_user import dispatch_consultation_email
"""

from .email_service import dispatch_consultation_email

__all__ = ["dispatch_consultation_email"]
