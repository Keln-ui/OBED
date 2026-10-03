import PyPDF2
import json
from .base_converter import BaseConverter
import logging

logger = logging.getLogger(__name__)


class JSONConverter(BaseConverter):
    """Converter for PDF to JSON"""
    
    def convert(self) -> bool:
        """Convert PDF to JSON"""
        try:
            if not self.validate_pdf():
                logger.error(f"Invalid PDF file: {self.pdf_path}")
                return False
            
            # Create output directory if it doesn't exist
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Extract text from PDF
            pages_data = []
            with open(self.pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for i, page in enumerate(pdf_reader.pages):
                    text = page.extract_text()
                    if text:
                        pages_data.append({
                            'page_number': i + 1,
                            'text': text,
                            'char_count': len(text)
                        })
            
            # Create JSON structure
            json_data = {
                'source_file': self.pdf_path.name,
                'total_pages': len(pages_data),
                'pages': pages_data
            }
            
            with open(self.output_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Successfully converted {self.pdf_path} to {self.output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error converting PDF to JSON: {str(e)}")
            return False