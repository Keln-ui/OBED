"""
Test script to check if email sending works.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'word_converter.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings

def test_email():
    """Test email sending functionality."""
    try:
        print(f"Email Backend: {settings.EMAIL_BACKEND}")
        print(f"Email Host: {settings.EMAIL_HOST}")
        print(f"Email Port: {settings.EMAIL_PORT}")
        print(f"Email User: {settings.EMAIL_HOST_USER}")
        print(f"Use SSL: {settings.EMAIL_USE_SSL}")
        print(f"Use TLS: {settings.EMAIL_USE_TLS}")
        print("\nSending test email...")

        send_mail(
            'Test Email from CoreSynch',
            'This is a test email to verify email sending works with your new domain email.',
            settings.DEFAULT_FROM_EMAIL,
            ['jomokelvin1143@gmail.com'],  # Send to yourself to test
            fail_silently=False,
        )

        print("SUCCESS: Email sent successfully!")
        print("Please check your inbox (and spam folder).")

    except Exception as e:
        print(f"ERROR: Failed to send email: {str(e)}")
        print("\nPossible issues:")
        print("1. Check SMTP server credentials")
        print("2. Check if the SMTP server requires authentication")
        print("3. Check firewall/network settings")

if __name__ == '__main__':
    test_email()
