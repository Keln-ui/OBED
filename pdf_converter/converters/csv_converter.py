import PyPDF2
import csv
from .base_converter import BaseConverter
import logging

logger = logging.getLogger(__name__)


class CSVConverter(BaseConverter):
    """Converter for PDF to CSV (extracts text with page numbers)"""
    
    def convert(self) -> bool:
        """Convert PDF to CSV"""
        try:
            if not self.validate_pdf():
                logger.error(f"Invalid PDF file: {self.pdf_path}")
                return False
            
            # Create output directory if it doesn't exist
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Extract text from PDF
            with open(self.pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                with open(self.output_path, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Page Number', 'Text Content', 'Character Count'])
                    
                    for i, page in enumerate(pdf_reader.pages):
                        text = page.extract_text()
                        if text:
                            # Clean text for CSV (remove newlines within content)
                            clean_text = text.replace('\n', ' ').replace('\r', ' ')
                            writer.writerow([i + 1, clean_text, len(text)])
            
            logger.info(f"Successfully converted {self.pdf_path} to {self.output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error converting PDF to CSV: {str(e)}")
            return False