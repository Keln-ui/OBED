# PDF to Word Converter

A Django-based web application that converts various types of PDF files to Word documents.

## Features

- Convert text-based PDFs to Word
- Convert image-based/scanned PDFs to Word (using OCR)
- Support for multiple PDF formats
- Simple web interface for file upload and conversion
- Download converted Word documents

## Installation

1. Install Python 3.8 or higher
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Install Tesseract OCR (required for scanned PDFs):
   - Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
   - Add Tesseract to your system PATH

4. For Word-to-PDF conversions that retain the document's page layout and styling, install LibreOffice and make `soffice` available on PATH. Without it, the built-in fallback converts text and tables but may not reproduce complex formatting exactly.

5. Run migrations:
   ```
   python manage.py migrate
   ```

6. Create superuser (optional):
   ```
   python manage.py createsuperuser
   ```

7. Run the development server:
   ```
   python manage.py runserver
   ```

8. Open your browser and navigate to http://academic.localhost:8000 or http://converter.localhost:8000

## Separate Academic and Converter Sites

The application serves two focused homepages from the same Django project:

- **Academic platform:** revision materials, teaching jobs, and scheme-of-work planning.
- **Document converter:** document conversion, free PDF conversions, and PDF utilities.

The sites link to each other, but each has its own hostname and focused navigation. For local development, the default hosts are `academic.localhost` and `converter.localhost` on port `8000`. The existing `http://127.0.0.1:8000` address shows the academic homepage. Sign in separately on each local hostname; browsers do not reliably accept cookies scoped to `.localhost`.

Staff users see a separate site dashboard at `/admin/dashboard/` on each subdomain: the academic host focuses on learning materials, schemes of work, and job approvals, while the converter host focuses on conversions and payments. Django Admin remains available separately at `/admin/`.

For hosting, point both subdomains to the same server and route both hostnames to this Django application. Configure the hostnames and HTTPS scheme in the environment:

```text
ACADEMIC_HOST=learn.example.com
CONVERTER_HOST=files.example.com
SITE_SCHEME=https
ALLOWED_HOSTS=learn.example.com,files.example.com
```

Set `SESSION_COOKIE_DOMAIN=.example.com` to share sign-in sessions and CSRF cookies between the two production subdomains. Use their common parent domain (not either individual subdomain). Without this setting, each subdomain has a separate browser session. Configure TLS and DNS for both subdomains at your hosting provider; this project does not create DNS records or deploy the server.

## Usage

1. Upload a PDF file using the web interface
2. Click "Convert to Word"
3. Download the converted Word document

## Project Structure

```
word_converter/
├── pdf_converter/          # Django app for PDF conversion
│   ├── converters/         # Conversion logic
│   ├── templates/          # HTML templates
│   └── ...
├── media/                  # Uploaded and converted files
├── static/                 # Static files (CSS, JS)
└── word_converter/         # Django project settings
```
