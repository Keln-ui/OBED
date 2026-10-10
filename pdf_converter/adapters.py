from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth.models import User
from allauth.exceptions import ImmediateHttpResponse
from django.http import HttpResponseRedirect
from django.contrib import messages


class CustomAccountAdapter(DefaultAccountAdapter):
    """Custom adapter to handle account creation and verification."""
    
    def save_user(self, request, user, form, commit=True):
        """
        Override to handle custom user fields during registration.
        """
        user = super().save_user(request, user, form, commit=False)
        
        # Email is already set by the parent method
        if commit:
            user.save()
        return user


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Custom adapter to handle Google OAuth social account creation."""
    
    def pre_social_login(self, request, sociallogin):
        """
        This hook is invoked before a social login is processed.
        We use it to automatically link existing accounts with the same email.
        """
        # If the social account already exists, do nothing
        if sociallogin.is_existing:
            return
        
        # If the email is already associated with a user, link the social account
        email = sociallogin.account.extra_data.get('email')
        if email:
            try:
                user = User.objects.get(email=email)
                # Link the social account to the existing user
                sociallogin.connect(request, user)
                messages.success(request, f'Your Google account has been linked to your existing account {user.email}!')
            except User.DoesNotExist:
                # User doesn't exist, will be created automatically
                pass
    
    def save_user(self, request, sociallogin, form=None):
        """
        Override to customize user creation from social account.
        """
        user = super().save_user(request, sociallogin, form=form)
        
        # Additional custom logic if needed
        # For example, setting a default username from email
        if not user.username:
            # Generate username from email
            email = sociallogin.account.extra_data.get('email', '')
            username = email.split('@')[0] if email else 'google_user'
            # Ensure username is unique
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}_{counter}"
                counter += 1
            user.username = username
        
        user.save()
        return user
