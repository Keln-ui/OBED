import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'word_converter.settings')
django.setup()

from django.contrib.auth.models import User
from django.db import connection

# Enable foreign key checking for this connection
cursor = connection.cursor()
cursor.execute("PRAGMA foreign_keys = ON;")
result = cursor.fetchone()
output = f"Foreign keys enabled: {result[0]}\n"

# Try creating a test user
output += "\nAttempting to create a test user...\n"
try:
    # First, let's see what users exist
    existing_users = User.objects.all()
    output += f"Existing users: {[u.username for u in existing_users]}\n"
    output += f"Existing user IDs: {[u.id for u in existing_users]}\n"
    
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
    output += f"SUCCESS: Created user with ID {test_user.id}\n"
    
    # Clean up
    test_user.delete()
    output += "Cleaned up test user\n"
    
except Exception as e:
    output += f"ERROR: {type(e).__name__}: {e}\n"
    import traceback
    output += traceback.format_exc()

cursor.close()

# Write output to file
with open('test_output.txt', 'w') as f:
    f.write(output)

print("Output written to test_output.txt")