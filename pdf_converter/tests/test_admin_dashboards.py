from types import SimpleNamespace
from unittest.mock import patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from pdf_converter import admin_views


@override_settings(
    ACADEMIC_HOST='academic.test',
    CONVERTER_HOST='converter.test',
)
class AdminDashboardRoutingTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.staff_user = SimpleNamespace(is_authenticated=True, is_staff=True)

    @patch('pdf_converter.admin_views._academic_admin_dashboard')
    @patch('pdf_converter.admin_views._converter_admin_dashboard')
    def test_academic_host_opens_academic_dashboard(
        self,
        converter_dashboard,
        academic_dashboard,
    ):
        academic_dashboard.return_value = HttpResponse('academic dashboard')
        request = self.factory.get('/admin/dashboard/', HTTP_HOST='academic.test')
        request.user = self.staff_user

        response = admin_views.admin_dashboard(request)

        self.assertEqual(response.content, b'academic dashboard')
        academic_dashboard.assert_called_once_with(request)
        converter_dashboard.assert_not_called()

    @patch('pdf_converter.admin_views._academic_admin_dashboard')
    @patch('pdf_converter.admin_views._converter_admin_dashboard')
    def test_converter_host_opens_converter_dashboard(
        self,
        converter_dashboard,
        academic_dashboard,
    ):
        converter_dashboard.return_value = HttpResponse('converter dashboard')
        request = self.factory.get(
            '/admin/dashboard/',
            HTTP_HOST='converter.test',
        )
        request.user = self.staff_user

        response = admin_views.admin_dashboard(request)

        self.assertEqual(response.content, b'converter dashboard')
        converter_dashboard.assert_called_once_with(request)
        academic_dashboard.assert_not_called()

    @patch('pdf_converter.admin_views._academic_admin_dashboard')
    @patch('pdf_converter.admin_views._converter_admin_dashboard')
    def test_loopback_host_uses_academic_dashboard(
        self,
        converter_dashboard,
        academic_dashboard,
    ):
        academic_dashboard.return_value = HttpResponse('academic dashboard')
        request = self.factory.get('/admin/dashboard/', HTTP_HOST='127.0.0.1:8000')
        request.user = self.staff_user

        response = admin_views.admin_dashboard(request)

        self.assertEqual(response.content, b'academic dashboard')
        academic_dashboard.assert_called_once_with(request)
        converter_dashboard.assert_not_called()
