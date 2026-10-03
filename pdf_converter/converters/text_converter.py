import PyPDF2
from .base_converter import BaseConverter
import logging

logger = logging.getLogger(__name__)


class TextConverter(BaseConverter):
    """Converter for PDF to plain text"""
    
    def convert(self) -> bool:
        """Convert PDF to plain text"""
        try:
            if not self.validate_pdf():
                logger.error(f"Invalid PDF file: {self.pdf_path}")
                return False
            
            # Create output directory if it doesn't exist
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Extract text from PDF
            text_content = []
            with open(self.pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text = page.extract_text()
                    if text:
                        text_content.append(text)
            
            # Write to text file
            with open(self.output_path, 'w', encoding='utf-8') as f:
                f.write('\n\n'.join(text_content))
            
            logger.info(f"Successfully converted {self.pdf_path} to {self.output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error converting PDF to text: {str(e)}")
            return False