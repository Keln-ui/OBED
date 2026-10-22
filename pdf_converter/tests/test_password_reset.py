import re

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


class PasswordResetConfirmTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='reset-user',
            email='reset@example.com',
            password='Old-password-123!',
        )
        self.uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        self.token = default_token_generator.make_token(self.user)
        self.confirm_url = reverse(
            'password_reset_confirm',
            kwargs={'uidb64': self.uid, 'token': self.token},
        )

    def test_email_reset_link_shows_redesigned_password_form(self):
        response = self.client.get(self.confirm_url, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/password_reset_confirm.html')
        self.assertContains(response, 'Choose a new password')
        self.assertContains(response, 'name="new_password1"')
        self.assertContains(response, 'name="new_password2"')

    def test_reset_link_is_valid_in_a_separate_browser_session(self):
        preview_client = Client()
        preview_response = preview_client.get(self.confirm_url)

        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(preview_response.get('Referrer-Policy'), 'no-referrer')
        self.assertContains(preview_response, 'Choose a new password')

        actual_browser = Client()
        actual_response = actual_browser.get(self.confirm_url)

        self.assertEqual(actual_response.status_code, 200)
        self.assertContains(actual_response, 'Choose a new password')
        self.assertNotContains(actual_response, 'This link has expired')

    def test_successful_reset_sets_password_and_logs_user_in(self):
        reset_form = self.client.get(self.confirm_url, follow=True)
        response = self.client.post(
            reset_form.request['PATH_INFO'],
            {
                'new_password1': 'CoreSynch-Unique-Password-89!',
                'new_password2': 'CoreSynch-Unique-Password-89!',
            },
        )

        self.assertRedirects(response, reverse('password_reset_complete'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('CoreSynch-Unique-Password-89!'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_reset_form_submission_passes_csrf_validation(self):
        client = Client(enforce_csrf_checks=True)
        response = client.get(self.confirm_url)
        self.assertEqual(response.status_code, 200)

        response = client.post(
            self.confirm_url,
            {
                'new_password1': 'CoreSynch-Unique-Password-89!',
                'new_password2': 'CoreSynch-Unique-Password-89!',
                'csrfmiddlewaretoken': client.cookies['csrftoken'].value,
            },
        )

        self.assertRedirects(response, reverse('password_reset_complete'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('CoreSynch-Unique-Password-89!'))

    def test_invalid_reset_link_shows_recovery_action(self):
        invalid_url = reverse(
            'password_reset_confirm',
            kwargs={'uidb64': self.uid, 'token': 'invalid-token'},
        )

        response = self.client.get(invalid_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This link has expired')
        self.assertContains(response, reverse('password_reset'))


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PasswordResetEmailTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user(
            username='mail-reset-user',
            email='mail-reset@example.com',
            password='Old-password-123!',
        )

    def test_reset_email_uses_the_domain_that_requested_it(self):
        response = self.client.post(
            reverse('password_reset'),
            {'email': 'mail-reset@example.com'},
            HTTP_HOST='academic.test',
        )

        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        email_body = mail.outbox[0].body
        self.assertIn('http://academic.test/accounts/reset/', email_body)
        self.assertNotIn('example.com/accounts/reset/', email_body)

        reset_link = re.search(
            r'http://academic\.test/accounts/reset/[^\s"<]+',
            email_body,
        ).group(0)
        response = self.client.get(
            reset_link.replace('http://academic.test', ''),
            HTTP_HOST='academic.test',
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Choose a new password')
        self.assertNotContains(response, 'This link has expired')
