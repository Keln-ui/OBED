"""
Test script to check password reset with actual users.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'word_converter.settings')
django.setup()

from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordResetForm
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

def test_password_reset():
    """Test password reset with actual users."""
    print("=== Registered Users ===")
    users = User.objects.all()
    if users:
        for user in users:
            print(f"- Username: {user.username}, Email: {user.email}, Active: {user.is_active}")
    else:
        print("No users found in database.")

    print("\n=== Testing Password Reset with macasdeborah@gmail.com ===")
    test_email = 'macasdeborah@gmail.com'

    if User.objects.filter(email=test_email).exists():
        print(f"Email found in database: {test_email}")

        form = PasswordResetForm({'email': test_email})
        if form.is_valid():
            try:
                form.save(
                    subject_template_name='registration/password_reset_subject.txt',
                    email_template_name='registration/password_reset_email.html',
                    html_email_template_name='registration/password_reset_email.html',
                    request=None,
                )
                print("SUCCESS: Password reset email sent!")
                print(f"Please check the inbox for: {test_email}")
            except Exception as e:
                print(f"ERROR: Failed to send password reset email: {str(e)}")
        else:
            print(f"ERROR: Form validation failed: {form.errors}")
    else:
        print(f"ERROR: Email not found in database: {test_email}")
        print("You need to register this email first before resetting password.")

if __name__ == '__main__':
    test_password_reset()
