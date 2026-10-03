import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'word_converter.settings')
django.setup()

from django.contrib.auth.models import User
from django.db import connection

# Enable foreign key checking for this connection
cursor = connection.cursor()
cursor.execute("PRAGMA foreign_keys = ON;")
result = cursor.fetchone()
print(f"Foreign keys enabled: {result[0]}")

# Try creating a test user
print("\nAttempting to create a test user...")
try:
    # First, let's see what users exist
    existing_users = User.objects.all()
    print(f"Existing users: {[u.username for u in existing_users]}")
    print(f"Existing user IDs: {[u.id for u in existing_users]}")
    
    # Try to create a new user
    test_user = User(
        username='test_user_admin',
        email='test@example.com',
        first_name='Test',
        last_name='User',
        is_staff=True,
        is_active=True
    )
    test_user.set_password('testpass123')
    test_user.save()
    print(f"SUCCESS: Created user with ID {test_user.id}")
    
    # Clean up
    test_user.delete()
    print("Cleaned up test user")
    
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

cursor.close()