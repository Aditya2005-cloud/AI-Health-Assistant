"""
email_notification_service/__init__.py
--------------------------------------
Gmail Email Service Package for Medivio.

Exposes the single top-level function the rest of the app needs:

    from email_notification_service import dispatch_consultation_email
"""

from .email_service import dispatch_consultation_email

__all__ = ["dispatch_consultation_email"]
