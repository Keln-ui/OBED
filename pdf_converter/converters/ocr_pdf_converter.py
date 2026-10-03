import PyPDF2
import json
import csv
import os
import io
import tempfile
import logging
import contextlib
from docx.shared import Pt
from .base_converter import BaseConverter

logger = logging.getLogger(__name__)


def clean_ocr_text(text: str) -> str:
    """
    Cleans up common OCR garbage errors from dotted/dashed lines on writing sheets.
    Replaces repetitive OCR noise characters with a clean dotted line.
    Also corrects common OCR errors like 'cm}' to 'cm³' and formatting errors.
    """
    import re
    words = text.split()
    cleaned_words = []
    noise_chars = set('cesoxandbv._-~*`')
    
    for w in words:
        w_clean = w.strip('(),.?!:;""\'\'')
        if len(w_clean) >= 12:
            unique_chars = set(w_clean.lower())
            noise_count = sum(1 for c in w_clean.lower() if c in noise_chars)
            noise_fraction = noise_count / len(w_clean)
            
            if noise_fraction >= 0.75 and len(unique_chars) <= 7:
                cleaned_words.append("........................................................")
                continue
        cleaned_words.append(w)
        
    res = " ".join(cleaned_words)
    while "........................................................ ........................................................" in res:
        res = res.replace("........................................................ ........................................................", "........................................................")
    
    # 1. Correct volume/area unit OCR misrecognition (e.g., cm}, cm3, dm}, dm3, m}, m3) to superscripts
    res = re.sub(r'\b(c|d)?m}', r'\1m³', res, flags=re.IGNORECASE)
    res = re.sub(r'\b(c|d)?m3\b', r'\1m³', res, flags=re.IGNORECASE)
    
    # 2. Correct question formatting where number runs into another number and unit: "16.200cm³" -> "16. 200 cm³"
    res = re.sub(r'\b(\d+)\.(\d+)\s*(cm³|dm³|m³|cm|dm|m)\b', r'\1. \2 \3', res, flags=re.IGNORECASE)
    
    # 3. Correct spacing between question number and text: "17.Explain" -> "17. Explain"
    res = re.sub(r'\b(\d+)\.([a-zA-Z])', r'\1. \2', res)
    
    # 4. Correct marks labels to standard format (e.g., "(3 marks)", "(1 mark)")
    # Correct plural/singular mark labels:
    # 1Imark, 11mark, IImark, 1Imarks, 1lmark, etc. -> (1 mark)
    res = re.sub(r'\(?\b1\s*[iI1l]\s*marks?\b\)?', r'(1 mark)', res, flags=re.IGNORECASE)
    # Match any roman numerals / isolated letters like i, I, l with mark -> (1 mark)
    res = re.sub(r'\(?\b[iI1l]\s*marks?\b\)?', r'(1 mark)', res, flags=re.IGNORECASE)
    # Match standalone 1 mark / 1mark -> (1 mark)
    res = re.sub(r'\(?\b1\s*marks?\b\)?', r'(1 mark)', res, flags=re.IGNORECASE)
    # Match other digit marks (e.g. 2marks, (3marks), 3 marks) -> (\1 marks)
    res = re.sub(r'\(?\b([2-9]|\d{2,})\s*marks?\b\)?', r'(\1 marks)', res, flags=re.IGNORECASE)
    
    return res


class OCRPDFConverter(BaseConverter):
    """Converter for image-based/scanned PDFs using OCR"""
    
    def __init__(self, pdf_path: str, output_path: str, output_format: str = 'docx'):
        super().__init__(pdf_path, output_path)
        self.output_format = output_format
    
    def convert(self) -> bool:
        """Convert scanned PDF to desired format using OCR"""
        temp_pdf_path = None
        
        try:
            if not self.validate_pdf():
                logger.error(f"Invalid PDF file: {self.pdf_path}")
                return False
            
            # Create output directory if it doesn't exist
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # First, try to OCR the PDF using ocrmypdf
            with self._get_temp_pdf_path() as temp_pdf_path:
                try:
                    # Run OCR on the PDF with optimized settings
                    import subprocess
                    result = subprocess.run(
                        ['ocrmypdf', '--output-type', 'pdf', '--force-ocr', '--optimize', '1',
                         str(self.pdf_path), temp_pdf_path],
                        capture_output=True,
                        text=True,
                        timeout=300  # 5 minute timeout
                    )
                    
                    if result.returncode == 0:
                        # OCR successful, convert based on format
                        return self._convert_ocr_pdf(temp_pdf_path)
                    else:
                        logger.warning(f"OCR failed with return code {result.returncode}: {result.stderr}")
                        # Fall back to direct pytesseract OCR
                        return self._convert_with_pytesseract()
                        
                except subprocess.TimeoutExpired:
                    logger.warning("OCR process timed out, falling back to pytesseract")
                    return self._convert_with_pytesseract()
                except FileNotFoundError:
                    # ocrmypdf not installed, fall back to pytesseract
                    logger.warning("ocrmypdf not found, falling back to pytesseract")
                    return self._convert_with_pytesseract()
            
        except Exception as e:
            logger.error(f"Error converting scanned PDF: {str(e)}")
            return False
    
    @contextlib.contextmanager
    def _get_temp_pdf_path(self):
        """Context manager for temporary PDF file"""
        import tempfile
        temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        temp_file.close()
        try:
            yield temp_file.name
        finally:
            if os.path.exists(temp_file.name):
                try:
                    os.remove(temp_file.name)
                except Exception as e:
                    logger.warning(f"Failed to remove temporary PDF {temp_file.name}: {e}")
    
    def _convert_ocr_pdf(self, ocr_pdf_path: str) -> bool:
        """Convert OCR'd PDF to the desired format"""
        try:
            # For all formats, use pytesseract directly on the original PDF for better text extraction
            # This ensures we get actual editable text rather than relying on pdf2docx
            return self._convert_with_pytesseract()
                
        except Exception as e:
            logger.error(f"Error in OCR conversion: {str(e)}")
            return False
    
    def _convert_with_pytesseract(self) -> bool:
        """Fallback OCR using pytesseract directly on PDF pages - extracts ALL text and images"""
        try:
            import fitz  # PyMuPDF
            from PIL import Image, ImageEnhance, ImageFilter
            import pytesseract
            
            tesseract_paths = [
                r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            ]
            for tp in tesseract_paths:
                if os.path.exists(tp):
                    pytesseract.pytesseract.tesseract_cmd = tp
                    break
            if not os.environ.get('TESSDATA_PREFIX'):
                tessdata = r'C:\Program Files\Tesseract-OCR\tessdata'
                if os.path.exists(tessdata):
                    os.environ['TESSDATA_PREFIX'] = tessdata
            
            try:
                pytesseract.get_tesseract_version()
            except EnvironmentError:
                logger.error("Tesseract OCR is not installed or not in PATH")
                self.error_message = "Tesseract OCR is not installed. Please install Tesseract OCR to convert scanned documents."
                return False
            
            pdf_document = fitz.open(str(self.pdf_path))
            total_pages = len(pdf_document)
            
            logger.info(f"Processing {total_pages} pages with pytesseract OCR (full extraction)")
            
            # Extract text and images from each page
            pages_data = []
            temp_images = []
            
            for page_num in range(total_pages):
                page = pdf_document[page_num]
                
                # Extract embedded images for this page
                page_images = []
                for img_index, img in enumerate(page.get_images()):
                    try:
                        xref = img[0]
                        pix = fitz.Pixmap(fitz.csRGB, fitz.Pixmap(pdf_document, xref))
                        if pix.n > 4:
                            pix = fitz.Pixmap(fitz.csRGB, pix)
                        
                        temp_img = os.path.join(
                            self.output_path.parent,
                            f".ocr_img_{self.pdf_path.stem}_{page_num}_{img_index}.png"
                        )
                        pix.save(temp_img)
                        page_images.append(temp_img)
                        temp_images.append(temp_img)
                    except Exception as img_err:
                        logger.warning(f"Could not extract image from page {page_num}: {img_err}")
                
                # OCR the page at high DPI
                zoom = 4.0
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat, dpi=300, alpha=False)
                
                pil_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                pil_img = pil_img.convert('L')
                enhancer = ImageEnhance.Contrast(pil_img)
                pil_img = enhancer.enhance(2.0)
                enhancer = ImageEnhance.Sharpness(pil_img)
                pil_img = enhancer.enhance(2.0)
                pil_img = pil_img.filter(ImageFilter.MedianFilter(size=1))
                
                page_text = None
                configs = [
                    r'--oem 3 --psm 6',
                    r'--oem 3 --psm 3',
                    r'--oem 1 --psm 6',
                    r'--oem 3 --psm 1',
                ]
                
                for config in configs:
                    try:
                        text_result = pytesseract.image_to_string(pil_img, config=config)
                        if text_result and text_result.strip():
                            page_text = text_result.strip()
                            break
                    except Exception:
                        continue
                
                if page_text:
                    page_text = clean_ocr_text(page_text)
                
                pages_data.append({
                    'text': page_text or '',
                    'images': page_images
                })
                
                logger.info(f"Page {page_num + 1}/{total_pages}: {len(page_text or '')} chars, {len(page_images)} images")
            
            pdf_document.close()
            
            # Write output based on format with embedded images
            if self.output_format == 'txt':
                combined = []
                for i, page_data in enumerate(pages_data):
                    if page_data['text']:
                        combined.append(f"=== Page {i+1} ===\n{page_data['text']}")
                with open(self.output_path, 'w', encoding='utf-8') as f:
                    f.write('\n\n'.join(combined))
            
            elif self.output_format == 'html':
                pages_html = []
                for i, page_data in enumerate(pages_data):
                    page_html = f'<div class="page" data-page="{i+1}">'
                    if page_data['text']:
                        page_html += page_data['text'].replace('&', '&').replace('<', '<').replace('>', '>')
                    if page_data['images']:
                        for img_path in page_data['images']:
                            page_html += f'<br><img src="{os.path.basename(img_path)}" style="max-width:100%;margin:10px 0;">'
                    page_html += '</div>'
                    pages_html.append(page_html)
                
                html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Converted PDF - {self.pdf_path.stem}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .page {{ margin-bottom: 40px; padding: 20px; border-bottom: 1px solid #ccc; }}
    </style>
</head>
<body>
    <h1>{self.pdf_path.stem}</h1>
    {''.join(pages_html)}
</body>
</html>'''
                with open(self.output_path, 'w', encoding='utf-8') as f:
                    f.write(html)
            
            elif self.output_format == 'json':
                json_data = {
                    'source_file': self.pdf_path.name,
                    'total_pages': len(pages_data),
                    'pages': [{'page_number': i+1, 'text': p['text'], 'image_count': len(p['images'])} 
                              for i, p in enumerate(pages_data)]
                }
                with open(self.output_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=2, ensure_ascii=False)
            
            elif self.output_format == 'csv':
                with open(self.output_path, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Page Number', 'Text Content', 'Image Count'])
                    for i, page_data in enumerate(pages_data):
                        writer.writerow([i + 1, page_data['text'].replace('\n', ' '), len(page_data['images'])])
            
            elif self.output_format == 'pptx':
                from pptx import Presentation
                from pptx.util import Inches, Pt
                
                prs = Presentation()
                prs.slide_width = Inches(10)
                prs.slide_height = Inches(7.5)
                
                for i, page_data in enumerate(pages_data):
                    blank_layout = prs.slide_layouts[6]
                    slide = prs.slides.add_slide(blank_layout)
                    
                    slide.shapes.add_textbox(
                        Inches(0.2), Inches(0.2), Inches(9.6), Inches(0.4)
                    ).text_frame.text = f"Page {i+1}"
                    
                    textbox = slide.shapes.add_textbox(
                        Inches(0.2), Inches(0.6), Inches(9.6), Inches(6.5)
                    )
                    text_frame = textbox.text_frame
                    text_frame.word_wrap = True
                    
                    if page_data['text']:
                        paragraphs = page_data['text'].strip().split('\n')
                        for j, para_text in enumerate(paragraphs):
                            if j == 0:
                                p = text_frame.paragraphs[0]
                            else:
                                p = text_frame.add_paragraph()
                            p.text = para_text
                            p.font.size = Pt(12)
                            p.font.name = 'Calibri'
                            p.space_after = Pt(4)
                    
                    for img_path in page_data['images']:
                        try:
                            slide.shapes.add_picture(img_path, Inches(0.5), Inches(6.5), Inches(9))
                        except:
                            pass
                
                prs.save(str(self.output_path))
            
            else:
                from docx import Document
                doc = Document()
                style = doc.styles['Normal']
                style.font.name = 'Calibri'
                style.font.size = Pt(11)
                
                for i, page_data in enumerate(pages_data):
                    p_header = doc.add_paragraph()
                    p_header.paragraph_format.space_after = Pt(6)
                    run = p_header.add_run(f"--- Page {i+1} ---")
                    run.bold = True
                    
                    for img_path in page_data['images']:
                        try:
                            p_img = doc.add_paragraph()
                            run = p_img.add_run()
                            run.add_picture(img_path, width=Inches(4.5))
                        except:
                            pass
                    
                    if page_data['text']:
                        for para_text in page_data['text'].split('\n'):
                            if para_text.strip():
                                p_text = doc.add_paragraph(para_text.strip())
                                p_text.paragraph_format.space_before = Pt(1)
                                p_text.paragraph_format.space_after = Pt(1)
                    else:
                        doc.add_paragraph("[No text detected on this page]")
                    
                    if i < len(pages_data) - 1:
                        doc.add_page_break()
                
                doc.save(str(self.output_path))
            
            # Clean up temp images
            for img_path in temp_images:
                try:
                    if os.path.exists(img_path):
                        os.remove(img_path)
                except:
                    pass
            
            logger.info(f"Successfully converted scanned PDF to {self.output_format} with full text and image extraction")
            return True
            
        except ImportError as e:
            logger.error(f"Missing required library for pytesseract OCR: {str(e)}")
            self.error_message = f"Missing library: {str(e)}. Please install pytesseract and Pillow."
            return False
        except Exception as e:
            logger.error(f"Error in pytesseract OCR conversion: {str(e)}")
            self.error_message = str(e)
            return False
    
    def _convert_standard(self) -> bool:
        """Fallback standard conversion"""
        try:
            if self.output_format in ['txt', 'html', 'json', 'csv']:
                # Extract text directly
                text_content = []
                with open(self.pdf_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    for page in pdf_reader.pages:
                        text = page.extract_text()
                        if text:
                            text_content.append(text)
                
                # If no text extracted, it's likely a scanned PDF - use pytesseract
                if not text_content:
                    logger.info("No text found in PDF, attempting pytesseract OCR")
                    return self._convert_with_pytesseract()
                
                if self.output_format == 'txt':
                    with open(self.output_path, 'w', encoding='utf-8') as f:
                        f.write('\n\n'.join(text_content))
                        
                elif self.output_format == 'html':
                    pages_html = []
                    for i, text in enumerate(text_content):
                        clean_text = text.replace('&', '&').replace('<', '<').replace('>', '>')
                        pages_html.append(f'<div class="page" data-page="{i+1}">{clean_text}</div>')
                    
                    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Converted PDF - {self.pdf_path.stem}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .page {{ margin-bottom: 40px; padding: 20px; border-bottom: 1px solid #ccc; }}
    </style>
</head>
<body>
    <h1>{self.pdf_path.stem}</h1>
    {''.join(pages_html)}
</body>
</html>'''
                    with open(self.output_path, 'w', encoding='utf-8') as f:
                        f.write(html)
                        
                elif self.output_format == 'json':
                    json_data = {
                        'source_file': self.pdf_path.name,
                        'total_pages': len(text_content),
                        'pages': [{'page_number': i+1, 'text': text} for i, text in enumerate(text_content)]
                    }
                    with open(self.output_path, 'w', encoding='utf-8') as f:
                        json.dump(json_data, f, indent=2, ensure_ascii=False)
                        
                elif self.output_format == 'csv':
                    with open(self.output_path, 'w', encoding='utf-8', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(['Page Number', 'Text Content'])
                        for i, text in enumerate(text_content):
                            writer.writerow([i + 1, text.replace('\n', ' ')])
                
                return True
            elif self.output_format == 'pptx':
                # For pptx, use PPTConverter
                from .ppt_converter import PPTConverter
                converter = PPTConverter(str(self.pdf_path), str(self.output_path))
                return converter.convert()
            else:
                # For docx/doc, first try pdf2docx, then fall back to pytesseract if it's scanned
                try:
                    from pdf2docx import Converter
                    cv = Converter(str(self.pdf_path))
                    cv.convert(str(self.output_path))
                    cv.close()
                    return True
                except Exception as pdf2docx_error:
                    logger.warning(f"pdf2docx failed, trying pytesseract OCR: {str(pdf2docx_error)}")
                    return self._convert_with_pytesseract()
                
        except Exception as e:
            logger.error(f"Error in fallback conversion: {str(e)}")
            return False
