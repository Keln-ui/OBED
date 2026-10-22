from unittest.mock import patch

from django.test import SimpleTestCase, override_settings


@override_settings(
    ACADEMIC_HOST='academic.test',
    CONVERTER_HOST='converter.test',
    SITE_SCHEME='https',
)
class HomepageRoutingTests(SimpleTestCase):
    @patch('pdf_converter.views.JobAdvertisement.objects.filter')
    @patch('revision.models.RevisionMaterial.objects.count', return_value=12)
    def test_academic_host_shows_academic_homepage(
        self,
        revision_count,
        jobs_filter,
    ):
        jobs_filter.return_value.exclude.return_value.order_by.return_value = []

        response = self.client.get('/', HTTP_HOST='academic.test')

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'academic_index.html')
        self.assertContains(response, 'Learn more.')
        self.assertContains(response, 'Revision materials')
        self.assertContains(response, 'Teaching opportunities')
        self.assertContains(response, 'https://converter.test/')
        self.assertEqual(response.content.decode().count('https://converter.test/'), 1)
        self.assertEqual(response.content.decode().count('Document Converter'), 1)
        self.assertNotIn('Document Converter', response.content.decode().split('</nav>', 1)[0])
        self.assertContains(response, 'Scheme of Work')

    def test_converter_host_shows_converter_homepage(self):
        response = self.client.get('/', HTTP_HOST='converter.test')

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'index.html')
        self.assertContains(response, 'Document Converter')
        self.assertContains(response, 'PDF Utilities')
        self.assertContains(response, 'https://academic.test/')
        self.assertEqual(response.content.decode().count('https://academic.test/'), 1)
        self.assertNotContains(response, 'Revision materials')
        self.assertNotContains(response, 'Teaching jobs')
