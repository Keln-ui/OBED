"""
Setup script to configure the default site for Django allauth.
Run this script after migrating to set up the site configuration.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'word_converter.settings')
django.setup()

from django.contrib.sites.models import Site

def setup_site():
    """Configure the default site for local development."""
    # Get or create the default site
    site, created = Site.objects.get_or_create(
        id=1,
        defaults={
            'domain': '127.0.0.1:8000',
            'name': 'Local Development'
        }
    )

    if created:
        print(f"Created new site: {site.domain}")
    else:
        print(f"Site already exists: {site.domain}")

    # Update the site to match local development
    site.domain = '127.0.0.1:8000'
    site.name = 'Local Development'
    site.save()

    print(f"Site configured: {site.domain} (ID: {site.id})")
    print("\nNext steps:")
    print("1. Go to http://127.0.0.1:8000/admin/")
    print("2. Navigate to Social Applications under Sites")
    print("3. Add a new Google OAuth application with your credentials")
    print("4. Select this site (127.0.0.1:8000) in the Sites field")

if __name__ == '__main__':
    setup_site()
