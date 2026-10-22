from .docx_image_converter import DocxImageConverter
from .ocr_pdf_converter import OCRPDFConverter
from .text_converter import TextConverter
from .html_converter import HTMLConverter
from .json_converter import JSONConverter
from .csv_converter import CSVConverter
from .image_converter import ImageConverter
from .ppt_converter import PPTConverter
from .text_pdf_converter import TextPDFConverter
import PyPDF2
import logging

logger = logging.getLogger(__name__)


class ConverterFactory:
    """Factory to determine the appropriate converter based on file type and output format"""
    
    SUPPORTED_FORMATS = ['docx', 'txt', 'html', 'json', 'csv', 'pptx']
    IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.tif', '.webp')
    
    @staticmethod
    def get_converter(pdf_path: str, output_path: str, output_format: str = 'docx', use_ocr: bool = False):
        """
        Get the appropriate converter for the file
        
        Args:
            pdf_path: Path to the PDF or image file
            output_path: Path for the output file
            output_format: Desired output format (docx, txt, html, json, csv, pptx)
            use_ocr: Force use of OCR converter
        
        Returns:
            Appropriate converter instance
        """
        # Validate output format
        if output_format not in ConverterFactory.SUPPORTED_FORMATS:
            logger.warning(f"Unsupported format '{output_format}', defaulting to docx")
            output_format = 'docx'
        
        # Check if the file is an image
        is_image = pdf_path.lower().endswith(ConverterFactory.IMAGE_EXTENSIONS)
        
        if is_image:
            logger.info(f"Detected image file, using ImageConverter for {output_format} format")
            return ImageConverter(pdf_path, output_path)
        
        # For pptx format, always use PPTConverter (handles both text and scanned PDFs)
        if output_format == 'pptx':
            logger.info(f"Using PPTConverter for pptx format")
            return PPTConverter(pdf_path, output_path)
        
        # Check if we should use OCR (either forced or because PDF is scanned)
        should_use_ocr = use_ocr
        
        if not should_use_ocr:
            # Check if PDF is likely scanned by trying to extract text
            try:
                with open(pdf_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    text_content = ""
                    total_pages = len(pdf_reader.pages)
                    
                    # Check first few pages for text (up to 5 pages or all pages if fewer)
                    pages_to_check = min(5, total_pages)
                    for page in pdf_reader.pages[:pages_to_check]:
                        extracted = page.extract_text()
                        if extracted:
                            text_content += extracted
                    
                    # Calculate average text per page
                    avg_text_per_page = len(text_content.strip()) / pages_to_check if pages_to_check > 0 else 0
                    
                    # If very little text found (less than 30 chars total or less than 10 chars per page),
                    # it's likely a scanned PDF
                    if len(text_content.strip()) < 30 or avg_text_per_page < 10:
                        logger.info(f"Detected scanned/image-based PDF (avg {avg_text_per_page:.1f} chars/page), using OCR converter")
                        should_use_ocr = True
                        
            except Exception as e:
                logger.warning(f"Error detecting PDF type: {str(e)}")
        
        # Use the layout-aware Word converter for editable Word documents.
        if output_format == 'docx':
            logger.info("Using DocxImageConverter for editable Word output with layout preservation")
            return DocxImageConverter(pdf_path, output_path, use_ocr=should_use_ocr)
        
        # For scanned PDFs with text-based formats, use OCR
        if should_use_ocr:
            logger.info(f"Using OCR converter for {output_format} format")
            return OCRPDFConverter(pdf_path, output_path, output_format)
        
        # Return appropriate converter based on format
        converters = {
            'txt': TextConverter,
            'html': HTMLConverter,
            'json': JSONConverter,
            'csv': CSVConverter,
        }
        
        converter_class = converters.get(output_format)
        if converter_class:
            logger.info(f"Using {converter_class.__name__} for {output_format} format")
            return converter_class(pdf_path, output_path)
        
        # Fallback
        logger.info(f"Using DocxImageConverter as fallback for {output_format}")
        return DocxImageConverter(pdf_path, output_path)
