"""
Test script to verify user registration and login flow.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'word_converter.settings')
django.setup()

from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from pdf_converter.forms import SimpleUserRegistrationForm
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

def test_registration():
    """Test user registration with auto-generated password."""
    print("=== Testing User Registration ===")

    # Test data
    test_username = 'testuser123'
    test_email = 'testuser@example.com'

    # Check if user already exists
    if User.objects.filter(username=test_username).exists():
        print(f"User '{test_username}' already exists. Deleting...")
        User.objects.filter(username=test_username).delete()

    print(f"\nCreating user: {test_username} ({test_email})")

    # Create form with test data
    form_data = {
        'username': test_username,
        'email': test_email,
    }

    form = SimpleUserRegistrationForm(data=form_data)
    if form.is_valid():
        # Save user and get auto-generated password
        user, password = form.save(commit=True)
        user.is_active = True
        user.save()

        print(f"User created successfully!")
        print(f"Username: {user.username}")
        print(f"Email: {user.email}")
        print(f"Auto-generated password: {password}")

        # Test authentication
        print("\n=== Testing Login ===")
        authenticated_user = authenticate(username=test_username, password=password)
        if authenticated_user:
            print(f"SUCCESS: User can log in with auto-generated password!")
        else:
            print(f"ERROR: Authentication failed!")

        # Test email sending
        print("\n=== Testing Registration Email ===")
        try:
            message = render_to_string('registration/registration_email.html', {
                'user': user,
                'password': password,
                'domain': '127.0.0.1:8000',
            })

            send_mail(
                'Welcome to CoreSynch - Your Account Credentials',
                message,
                settings.DEFAULT_FROM_EMAIL,
                [test_email],
                fail_silently=False,
                html_message=message,
            )
            print(f"SUCCESS: Registration email sent to {test_email}")
            print(f"Note: Email sent to test address - won't actually be delivered")
        except Exception as e:
            print(f"ERROR: Failed to send registration email: {str(e)}")

        # Clean up test user
        print("\n=== Cleaning Up ===")
        user.delete()
        print(f"Test user '{test_username}' deleted")

    else:
        print(f"ERROR: Form validation failed: {form.errors}")

if __name__ == '__main__':
    test_registration()
