import PyPDF2
from .base_converter import BaseConverter
import logging

logger = logging.getLogger(__name__)


class HTMLConverter(BaseConverter):
    """Converter for PDF to HTML"""
    
    def convert(self) -> bool:
        """Convert PDF to HTML"""
        try:
            if not self.validate_pdf():
                logger.error(f"Invalid PDF file: {self.pdf_path}")
                return False
            
            # Create output directory if it doesn't exist
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Extract text from PDF
            pages_content = []
            with open(self.pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for i, page in enumerate(pdf_reader.pages):
                    text = page.extract_text()
                    if text:
                        # Escape HTML special characters
                        text = text.replace('&', '&').replace('<', '<').replace('>', '>')
                        pages_content.append(f'<div class="page" data-page="{i+1}">{text}</div>')
            
            # Create HTML document
            html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Converted PDF - {self.pdf_path.stem}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .page {{ margin-bottom: 40px; padding: 20px; border-bottom: 1px solid #ccc; }}
        .page pre {{ white-space: pre-wrap; word-wrap: break-word; }}
    </style>
</head>
<body>
    <h1>{self.pdf_path.stem}</h1>
    {''.join(pages_content)}
</body>
</html>'''
            
            with open(self.output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"Successfully converted {self.pdf_path} to {self.output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error converting PDF to HTML: {str(e)}")
            return False