import io
import os
import tempfile
import zipfile
from unittest.mock import patch

import fitz
from PIL import Image
from PyPDF2 import PdfReader, PdfWriter
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from reportlab.pdfgen import canvas


class PDFToolTests(TestCase):
    tool_urls = {
        'merge': 'pdf_tool_merge',
        'split': 'pdf_tool_split',
        'compress': 'pdf_tool_compress',
        'rotate': 'pdf_tool_rotate',
        'watermark': 'pdf_tool_watermark',
        'flatten': 'pdf_tool_flatten',
        'resize': 'pdf_tool_resize',
        'unlock': 'pdf_tool_unlock',
        'protect': 'pdf_tool_protect',
        'crop': 'pdf_tool_crop',
        'organize': 'pdf_tool_organize',
        'extract_image': 'pdf_tool_extract_image',
        'page_remover': 'pdf_tool_page_remover',
        'extract_pages': 'pdf_tool_extract_pages',
    }

    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.media_settings = patch('django.conf.settings.MEDIA_ROOT', self.media_dir.name)
        self.media_settings.start()
        self.client = Client()
        self.pdf_bytes = self.make_pdf()

    def tearDown(self):
        self.media_settings.stop()
        self.media_dir.cleanup()

    @staticmethod
    def make_pdf(page_count=3):
        output = io.BytesIO()
        document = canvas.Canvas(output)
        for page_number in range(1, page_count + 1):
            document.drawString(72, 720, f'PAGE {page_number}')
            document.showPage()
        document.save()
        return output.getvalue()

    @staticmethod
    def upload(content=None, name='sample.pdf'):
        return SimpleUploadedFile(name, content or PDFToolTests.make_pdf(), content_type='application/pdf')

    def post_tool(self, tool, files=None, data=None):
        payload = dict(data or {})
        if files is None:
            files = self.upload()
        elif not isinstance(files, list) and not hasattr(files, 'read'):
            files = self.upload(files)
        payload['pdf_files'] = files
        return self.client.post(reverse(self.tool_urls[tool]), payload)

    def output_path(self, response):
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()
        self.assertTrue(result.get('success'), result)
        return os.path.join(self.media_dir.name, 'converted', result['filename'])

    def test_merge_combines_uploaded_documents(self):
        response = self.post_tool('merge', [self.upload(), self.upload(self.make_pdf(1), 'second.pdf')])
        self.assertEqual(len(PdfReader(self.output_path(response)).pages), 4)

    def test_split_creates_a_pdf_per_selected_page(self):
        response = self.post_tool('split', data={'page_range': '1,3'})
        path = self.output_path(response)
        with zipfile.ZipFile(path) as archive:
            self.assertEqual(archive.namelist(), ['page_1.pdf', 'page_3.pdf'])
            self.assertEqual(len(PdfReader(io.BytesIO(archive.read('page_3.pdf'))).pages), 1)

    def test_compress_writes_a_valid_pdf(self):
        path = self.output_path(self.post_tool('compress'))
        self.assertEqual(len(PdfReader(path).pages), 3)

    def test_rotate_applies_selected_rotation(self):
        path = self.output_path(self.post_tool('rotate', data={'rotation': '270'}))
        self.assertEqual(PdfReader(path).pages[0].rotation, 270)

    def test_watermark_creates_output(self):
        path = self.output_path(self.post_tool('watermark', data={'watermark_text': 'TEST'}))
        reader = PdfReader(path)
        self.assertEqual(len(reader.pages), 3)
        self.assertIn('TEST', reader.pages[0].extract_text())

    def test_flatten_renders_page_content_into_page_images(self):
        path = self.output_path(self.post_tool('flatten'))
        flattened = fitz.open(path)
        try:
            self.assertEqual(len(flattened), 3)
            self.assertTrue(all(page.get_images() for page in flattened))
        finally:
            flattened.close()

    def test_resize_changes_page_dimensions(self):
        path = self.output_path(self.post_tool('resize', data={'scale': '50'}))
        original_width = float(PdfReader(io.BytesIO(self.pdf_bytes)).pages[0].mediabox.width)
        self.assertAlmostEqual(float(PdfReader(path).pages[0].mediabox.width), original_width / 2)

    def test_unlock_copies_unencrypted_pdf(self):
        path = self.output_path(self.post_tool('unlock', data={'password': ''}))
        self.assertFalse(PdfReader(path).is_encrypted)

    def test_unlock_decrypts_protected_pdf_and_rejects_wrong_password(self):
        writer = PdfWriter()
        writer.append_pages_from_reader(PdfReader(io.BytesIO(self.pdf_bytes)))
        writer.encrypt('secret')
        encrypted_pdf = io.BytesIO()
        writer.write(encrypted_pdf)

        wrong_password = self.post_tool('unlock', encrypted_pdf.getvalue(), {'password': 'wrong'})
        self.assertEqual(wrong_password.status_code, 400)
        unlocked = self.post_tool('unlock', encrypted_pdf.getvalue(), {'password': 'secret'})
        self.assertFalse(PdfReader(self.output_path(unlocked)).is_encrypted)

    def test_protect_encrypts_output(self):
        path = self.output_path(self.post_tool('protect', data={'password': 'secret'}))
        self.assertTrue(PdfReader(path).is_encrypted)

    def test_crop_changes_page_bounds(self):
        path = self.output_path(self.post_tool('crop', data={'crop_box': '0,0,300,400'}))
        page = PdfReader(path).pages[0]
        self.assertEqual(float(page.mediabox.width), 300)
        self.assertEqual(float(page.mediabox.height), 400)

    def test_organize_reorders_pages(self):
        path = self.output_path(self.post_tool('organize', data={'page_order': '3,1,2'}))
        reader = PdfReader(path)
        self.assertIn('PAGE 3', reader.pages[0].extract_text())
        self.assertIn('PAGE 1', reader.pages[1].extract_text())

    def test_extract_image_returns_zip_archive(self):
        image_data = io.BytesIO()
        Image.new('RGB', (10, 10), color='red').save(image_data, format='PNG')
        source = fitz.open()
        page = source.new_page()
        page.insert_image(page.rect, stream=image_data.getvalue())
        pdf_data = source.tobytes()
        source.close()

        path = self.output_path(self.post_tool('extract_image', pdf_data))
        with zipfile.ZipFile(path) as archive:
            self.assertTrue(archive.namelist())

    def test_page_remover_and_extract_pages_select_requested_pages(self):
        removed = self.output_path(self.post_tool('page_remover', data={'page_range': '2'}))
        self.assertEqual(len(PdfReader(removed).pages), 2)
        extracted = self.output_path(self.post_tool('extract_pages', data={'page_range': '3,1'}))
        pages = PdfReader(extracted).pages
        self.assertEqual(len(pages), 2)
        self.assertIn('PAGE 3', pages[0].extract_text())

    def test_invalid_page_range_is_reported_as_bad_request(self):
        response = self.post_tool('extract_pages', data={'page_range': '1-9'})
        self.assertEqual(response.status_code, 400)
