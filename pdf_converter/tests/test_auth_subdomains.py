from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.conf import settings
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import Client, RequestFactory, SimpleTestCase, override_settings
from allauth.socialaccount.models import SocialApp


@override_settings(
    ACADEMIC_HOST='academic.test',
    CONVERTER_HOST='converter.test',
    SITE_SCHEME='https',
)
class AuthenticationSubdomainTests(SimpleTestCase):
    @patch('allauth.socialaccount.adapter.get_adapter')
    def test_google_login_without_provider_config_redirects_with_message(
        self,
        get_adapter,
    ):
        get_adapter.return_value.get_app.side_effect = SocialApp.DoesNotExist

        response = self.client.get(
            '/google-login/',
            HTTP_HOST='academic.test',
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain, [('/login/?google_unavailable=1', 302)])
        self.assertContains(response, 'Google sign-in is not configured yet')

    @patch('allauth.socialaccount.adapter.get_adapter')
    def test_google_login_with_provider_config_redirects_to_allauth(
        self,
        get_adapter,
    ):
        get_adapter.return_value.get_app.return_value = object()

        response = self.client.get(
            '/google-login/',
            HTTP_HOST='academic.test',
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/accounts/google/login/')

    def test_sign_in_and_registration_pages_load_on_both_hosts(self):
        for host in ('academic.test', 'converter.test'):
            with self.subTest(host=host):
                login_response = self.client.get('/login/', HTTP_HOST=host)
                registration_response = self.client.get(
                    '/register/user/',
                    HTTP_HOST=host,
                )

                self.assertEqual(login_response.status_code, 200)
                self.assertTemplateUsed(login_response, 'registration/login.html')
                self.assertEqual(registration_response.status_code, 200)
                self.assertTemplateUsed(
                    registration_response,
                    'registration/user_register.html',
                )
                self.assertContains(registration_response, 'Create your account')
                self.assertContains(registration_response, 'name="username"')
                self.assertContains(registration_response, 'name="email"')
                self.assertContains(registration_response, 'name="password1"')
                self.assertContains(registration_response, 'name="password2"')
                self.assertContains(
                    registration_response,
                    'Choose a strong password',
                )
                self.assertContains(registration_response, 'Sign up with Google')

    @override_settings(
        CSRF_TRUSTED_ORIGINS=[
            'https://academic.test',
            'https://converter.test',
        ],
        CSRF_COOKIE_DOMAIN='.test',
    )
    def test_auth_forms_accept_post_from_either_subdomain(self):
        with patch('pdf_converter.views.User.objects.filter') as user_filter:
            user_filter.return_value.first.return_value = None
            self._assert_auth_post_from_trusted_subdomain()

    def _assert_auth_post_from_trusted_subdomain(self):
        client = Client(enforce_csrf_checks=True)
        response = client.get('/login/', HTTP_HOST='converter.test')
        csrf_token = response.cookies['csrftoken'].value

        response = client.post(
            '/login/',
            {'email': 'unknown@example.com', 'password': 'wrong', 'csrfmiddlewaretoken': csrf_token},
            HTTP_HOST='converter.test',
            HTTP_ORIGIN='https://academic.test',
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid email or password')
        response = client.post(
            '/login/',
            {'email': 'unknown@example.com', 'password': 'wrong', 'csrfmiddlewaretoken': csrf_token},
            HTTP_HOST='converter.test',
            HTTP_ORIGIN='https://untrusted.test',
        )
        self.assertEqual(response.status_code, 403)

    @patch('pdf_converter.views.login')
    @patch('pdf_converter.views.authenticate')
    @patch('pdf_converter.views.User.objects.filter')
    def test_login_authenticates_by_case_insensitive_email_and_password(
        self,
        user_filter,
        authenticate,
        login,
    ):
        user = SimpleNamespace(username='learner', is_active=True)
        user_filter.return_value.first.return_value = user
        authenticate.return_value = user

        response = self.client.post(
            '/login/',
            {'email': 'LEARNER@example.com', 'password': 'chosen-password'},
            HTTP_HOST='academic.test',
        )

        user_filter.assert_called_once_with(email__iexact='LEARNER@example.com')
        authenticate.assert_called_once_with(
            response.wsgi_request,
            username='learner',
            password='chosen-password',
        )
        login.assert_called_once_with(response.wsgi_request, user)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/')

    @patch('django.template.loader.render_to_string', return_value='welcome')
    @patch('django.contrib.sites.shortcuts.get_current_site')
    @patch('django.core.mail.send_mail', side_effect=RuntimeError('SMTP unavailable'))
    @patch('pdf_converter.forms.SimpleUserRegistrationForm')
    def test_email_failure_does_not_delete_new_account(
        self,
        registration_form,
        send_mail,
        get_current_site,
        render_to_string,
    ):
        user = SimpleNamespace(
            pk=7,
            email='learner@example.com',
            username='learner',
            save=Mock(),
            delete=Mock(),
        )
        form = registration_form.return_value
        form.is_valid.return_value = True
        form.save.return_value = user
        get_current_site.return_value.domain = 'academic.test'

        response = self.client.post(
            '/register/user/',
            {
                'username': 'learner',
                'email': 'learner@example.com',
                'password1': 'Strong-pass-123',
                'password2': 'Strong-pass-123',
            },
            HTTP_HOST='academic.test',
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain, [('/login/', 302)])
        user.delete.assert_not_called()
        user.save.assert_called_once_with()
        send_mail.assert_called_once()

    @override_settings(
        SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies',
    )
    def test_local_session_cookie_is_host_only_for_browser_compatibility(self):
        self.assertIsNone(settings.SESSION_COOKIE_DOMAIN)
        request = RequestFactory().get(
            '/',
            HTTP_HOST='academic.localhost',
        )
        middleware = SessionMiddleware(lambda request: HttpResponse())
        middleware.process_request(request)
        request.session['authenticated'] = True

        response = middleware.process_response(request, HttpResponse())

        self.assertEqual(response.cookies[settings.SESSION_COOKIE_NAME]['domain'], '')

    def test_local_csrf_cookie_is_host_only_for_browser_compatibility(self):
        self.assertIsNone(settings.CSRF_COOKIE_DOMAIN)
