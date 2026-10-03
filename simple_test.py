import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'word_converter.settings')
django.setup()

from django.contrib.auth.models import User

print("Django setup complete")
print(f"User model: {User}")

try:
    users = User.objects.all()
    print(f"Current users count: {users.count()}")
    for u in users:
        print(f"  - {u.username} (ID: {u.id})")
    
    print("\nCreating new user...")
    user = User.objects.create_user(
        username='testuser123',
        email='test@test.com',
        password='testpass123'
    )
    print(f"Created user: {user.username} (ID: {user.id})")
    
    print("\nSUCCESS: User creation works!")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()