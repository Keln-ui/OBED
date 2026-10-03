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

4. Run migrations:
   ```
   python manage.py migrate
   ```

5. Create superuser (optional):
   ```
   python manage.py createsuperuser
   ```

6. Run the development server:
   ```
   python manage.py runserver
   ```

7. Open your browser and navigate to http://127.0.0.1:8000

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
