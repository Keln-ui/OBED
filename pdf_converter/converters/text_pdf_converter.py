from pdf2docx import Converter
from .base_converter import BaseConverter
import logging

logger = logging.getLogger(__name__)


class TextPDFConverter(BaseConverter):
    """Converter for text-based PDFs using pdf2docx"""
    
    def convert(self) -> bool:
        """Convert text-based PDF to Word"""
        try:
            if not self.validate_pdf():
                logger.error(f"Invalid PDF file: {self.pdf_path}")
                return False
            
            # Create output directory if it doesn't exist
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert PDF to Word
            cv = Converter(str(self.pdf_path))
            cv.convert(str(self.output_path))
            cv.close()
            
            logger.info(f"Successfully converted {self.pdf_path} to {self.output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error converting PDF to Word: {str(e)}")
            return False
