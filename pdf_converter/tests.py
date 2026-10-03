from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PyPDF2 import PdfWriter


class PdfToolTests(TestCase):
    def test_merge_pdfs_returns_download_url(self):
        def build_pdf(name):
            writer = PdfWriter()
            page = writer.add_blank_page(width=72, height=72)
            writer.write(BytesIO())
            output = BytesIO()
            writer.write(output)
            output.seek(0)
            return SimpleUploadedFile(name, output.getvalue(), content_type='application/pdf')

        response = self.client.post(
            '/pdf-tools/merge/',
            {
                'pdf_files': [build_pdf('one.pdf'), build_pdf('two.pdf')],
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('download_url', data)
