"""
Test sending password reset to multiple email addresses.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'word_converter.settings')
django.setup()

from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordResetForm

def test_multiple_emails():
    """Test password reset with all registered emails."""
    print("=== Testing Password Reset for All Users ===")

    users = User.objects.exclude(email='').exclude(email__isnull=True)

    for user in users:
        email = user.email
        print(f"\nTesting: {email}")

        form = PasswordResetForm({'email': email})
        if form.is_valid():
            try:
                form.save(
                    subject_template_name='registration/password_reset_subject.txt',
                    email_template_name='registration/password_reset_email.html',
                    html_email_template_name='registration/password_reset_email.html',
                    request=None,
                )
                print(f"  SUCCESS: Email sent to {email}")
            except Exception as e:
                print(f"  ERROR: {str(e)}")
        else:
            print(f"  ERROR: Form validation failed: {form.errors}")

if __name__ == '__main__':
    test_multiple_emails()
