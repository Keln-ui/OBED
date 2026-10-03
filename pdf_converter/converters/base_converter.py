from abc import ABC, abstractmethod
from pathlib import Path


class BaseConverter(ABC):
    """Base class for PDF to Word converters"""
    
    def __init__(self, pdf_path: str, output_path: str):
        self.pdf_path = Path(pdf_path)
        self.output_path = Path(output_path)
    
    @abstractmethod
    def convert(self) -> bool:
        """Convert PDF to Word. Returns True if successful."""
        pass
    
    def validate_pdf(self) -> bool:
        """Validate that the PDF file exists and is readable"""
        return self.pdf_path.exists() and self.pdf_path.suffix.lower() == '.pdf'
