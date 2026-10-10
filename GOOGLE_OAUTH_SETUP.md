# Google OAuth Setup Instructions

This guide will help you set up Google OAuth for your application so users can sign in with their Google account.

## Step 1: Create a Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Sign in with your Google account
3. Click on the project dropdown at the top and select "New Project"
4. Enter a project name (e.g., "Word Converter App")
5. Click "Create"

## Step 2: Enable Google+ API

1. In the Google Cloud Console, navigate to:
   - APIs & Services > Library
2. Search for "Google+ API" or "Google Identity"
3. Click on it and click "Enable"

## Step 3: Configure OAuth Consent Screen

1. Navigate to: APIs & Services > OAuth consent screen
2. Choose "External" user type (for testing)
3. Fill in the required fields:
   - App name: "Word Converter"
   - User support email: your email
   - Developer contact information: your email
4. Click "Save and Continue"
5. Skip the "Scopes" section (click "Save and Continue")
6. Add test users (your email address for testing)
7. Click "Save and Continue"

## Step 4: Create OAuth 2.0 Credentials

1. Navigate to: APIs & Services > Credentials
2. Click "Create Credentials" > "OAuth client ID"
3. Application type: "Web application"
4. Name: "Word Converter Web Client"
5. Authorized redirect URIs (add these):
   - For local development:
     - `http://127.0.0.1:8000/accounts/google/login/callback/`
     - `http://localhost:8000/accounts/google/login/callback/`
   - For production (replace with your domain):
     - `https://yourdomain.com/accounts/google/login/callback/`
6. Click "Create"

## Step 5: Copy Your Credentials

After creating the OAuth client, you'll see:
- **Client ID**: Copy this
- **Client Secret**: Copy this (click the eye icon to reveal)

## Step 6: Configure Your Django Application

### Option A: Using Django Admin (Recommended)

1. Start your Django server: `python manage.py runserver`
2. Go to http://127.0.0.1:8000/admin/
3. Log in with your admin account
4. Navigate to "Social Applications" under "Sites"
5. Click "Add Social Application"
6. Fill in:
   - **Provider**: Google
   - **Name**: Google OAuth
   - **Client id**: Your Google Client ID
   - **Secret key**: Your Google Client Secret
   - **Key**: (leave empty, will be auto-generated)
7. Under "Sites", select your site (typically "example.com" or localhost)
   - If you don't see a site, go to "Sites" in admin and add:
     - Domain: `127.0.0.1:8000` or `localhost:8000`
     - Name: `localhost`
     - Display name: `Local Development`
8. Click "Save"

### Option B: Using Environment Variables (Production)

Add these to your environment or `.env` file:

```bash
GOOGLE_OAUTH_CLIENT_ID=your_client_id_here
GOOGLE_OAUTH_CLIENT_SECRET=your_client_secret_here
```

Then update your `settings.py` to read from environment variables (optional, more secure for production).

## Step 7: Test the Setup

1. Restart your Django server
2. Navigate to http://127.0.0.1:8000/login/
3. Click the "Sign in with Google" button
4. You should be redirected to Google's OAuth consent screen
5. Sign in with your Google account
6. You should be redirected back to your application and logged in

## Troubleshooting

### "Redirect URI mismatch" error
- Make sure the redirect URI in Google Cloud Console exactly matches what's in your Django settings
- Check for trailing slashes and protocol (http vs https)

### "Social Application not found" error
- Make sure you've created the Social Application in Django admin
- Ensure the site is associated with the Social Application
- Check that SITE_ID in settings.py matches your site's ID in Django admin

### Email verification issues
- If you want to require email verification, change `ACCOUNT_EMAIL_VERIFICATION` to `'mandatory'` in settings.py
- For development, `'none'` is recommended to skip verification

## Security Notes

- **Never commit your Google Client Secret to version control**
- Use environment variables for production deployments
- Restrict your OAuth client to authorized domains only
- Keep your test user list updated during development
- Enable Google+ API in production environment

## Additional Resources

- [Django Allauth Documentation](https://django-allauth.readthedocs.io/)
- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Google Cloud Console](https://console.cloud.google.com/)
