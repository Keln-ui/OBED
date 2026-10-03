"""
DocxImageConverter - Converts PDFs to fully editable DOCX/DOC files.

For scanned/image PDFs (like CHEMPP1.pdf):
  - Each page renders BOTH as high-resolution IMAGE and OCR-extracted TEXT
  - Diagrams, tables, charts, pictures preserved as embedded images
  - ALL text extracted via OCR and placed directly in document (fully selectable/editable)
  - Result: Entire document is editable - you can select and edit ALL text

For text-based PDFs:
  - Uses pdf2docx for clean text extraction with layout preservation
  - Falls back to hybrid if pdf2docx produces insufficient editable content
"""
import os
import tempfile
import logging
import io
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
    res = re.sub(r'(\d+)\s*(c|d)?m(?:3|})', r'\1 \2m³', res, flags=re.IGNORECASE)
    res = re.sub(r'\b(c|d)?m(?:3|})', r'\1m³', res, flags=re.IGNORECASE)
    
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


class DocxImageConverter(BaseConverter):
    """
    Converts PDFs to Word documents with BOTH:
    - Full visual preservation (page images for diagrams, pictures, formatting)
    - Fully editable text (OCR extracted, selectable in Word)
    """
    
    def __init__(self, pdf_path: str, output_path: str, use_ocr: bool = False):
        super().__init__(pdf_path, output_path)
        self.use_ocr = use_ocr
        
    def convert(self) -> bool:
        """Convert PDF to fully editable docx with all visual content preserved"""
        try:
            if not self.validate_pdf():
                logger.error(f"Invalid PDF file: {self.pdf_path}")
                return False
            
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Step 1: If not forcing OCR, try pdf2docx first (best for preserving editable vector graphics/drawings from Word)
            if not self.use_ocr:
                logger.info("Attempting pdf2docx conversion first to preserve editable layouts and drawings")
                if self._try_pdf2docx():
                    logger.info("Successfully converted PDF using pdf2docx")
                    return True
            
            # Step 2: Try flowing layout conversion (most editable format with text and inline diagrams)
            if self._try_flowing_layout_conversion():
                logger.info("Successfully converted PDF using flowing layout conversion")
                return True
            
            # Step 3: Try pdf2docx as fallback if we haven't tried it yet
            if self.use_ocr:
                if self._try_pdf2docx():
                    return True
            
            # Step 4: Hybrid approach - page images + editable OCR text
            # This preserves ALL visual content (diagrams, images, tables) AND gives editable text
            if self._try_hybrid_image_plus_text():
                logger.info(f"Hybrid conversion: visual content + editable text")
                return True
            
            # Step 5: Pure page images (fallback)
            logger.warning("Falling back to page image conversion")
            return self._fallback_page_images()
            
        except Exception as e:
            logger.error(f"Error converting PDF: {str(e)}")
            return False
            
    def _try_flowing_layout_conversion(self) -> bool:
        """
        Converts PDF into a 100% editable Word document with flowing layout.
        Extracts all text as body paragraphs and diagrams as inline cropped images.
        """
        try:
            import fitz
            from PIL import Image, ImageDraw
            import pytesseract
            from docx import Document
            from docx.shared import Inches, Pt, Cm
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            
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
                logger.warning("Tesseract not available for flowing layout conversion")
                return False
                
            pdf = fitz.open(str(self.pdf_path))
            total_pages = len(pdf)
            logger.info(f"Flowing layout conversion starting: {total_pages} pages")
            
            doc = Document()
            # Set page margins
            for section in doc.sections:
                section.top_margin = Cm(2.0)
                section.bottom_margin = Cm(2.0)
                section.left_margin = Cm(2.0)
                section.right_margin = Cm(2.0)
                
            total_text_chars = 0
            temp_images = []
            
            try:
                for page_num in range(total_pages):
                    page = pdf[page_num]
                    page_rect = page.rect
                    page_width = page_rect.width
                    page_height = page_rect.height
                    
                    # 1. Extract text blocks and bounding boxes
                    text_blocks = []
                    raw_blocks = page.get_text("blocks")
                    for b in raw_blocks:
                        # block format: (x0, y0, x1, y1, text, block_no, block_type)
                        b_text = b[4].strip()
                        if b_text and b[6] == 0:  # Text block type
                            text_blocks.append({
                                'type': 'text',
                                'bbox': (b[0], b[1], b[2], b[3]),
                                'text': b_text
                            })
                    
                    # Render page at 150 DPI for layout analysis
                    zoom = 150.0 / 72.0
                    mat = fitz.Matrix(zoom, zoom)
                    pix = page.get_pixmap(matrix=mat, alpha=False)
                    page_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    
                    # If no text blocks found via standard extraction, run OCR to get text and positions
                    if not text_blocks:
                        try:
                            ocr_data = pytesseract.image_to_data(page_img, output_type=pytesseract.Output.DICT)
                            blocks_dict = {}
                            n_boxes = len(ocr_data['text'])
                            for i in range(n_boxes):
                                word = ocr_data['text'][i].strip()
                                if not word:
                                    continue
                                
                                block_num = ocr_data['block_num'][i]
                                left = ocr_data['left'][i]
                                top = ocr_data['top'][i]
                                width = ocr_data['width'][i]
                                height = ocr_data['height'][i]
                                
                                # Scale back to page points (150 DPI)
                                scale = 72.0 / 150.0
                                x0 = left * scale
                                y0 = top * scale
                                x1 = (left + width) * scale
                                y1 = (top + height) * scale
                                
                                if block_num not in blocks_dict:
                                    blocks_dict[block_num] = {
                                        'words': [],
                                        'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1
                                    }
                                blocks_dict[block_num]['words'].append(word)
                                blocks_dict[block_num]['x0'] = min(blocks_dict[block_num]['x0'], x0)
                                blocks_dict[block_num]['y0'] = min(blocks_dict[block_num]['y0'], y0)
                                blocks_dict[block_num]['x1'] = max(blocks_dict[block_num]['x1'], x1)
                                blocks_dict[block_num]['y1'] = max(blocks_dict[block_num]['y1'], y1)
                            
                            for b_num, b_data in blocks_dict.items():
                                block_text = " ".join(b_data['words']).strip()
                                if block_text:
                                    text_blocks.append({
                                        'type': 'text',
                                        'bbox': (b_data['x0'], b_data['y0'], b_data['x1'], b_data['y1']),
                                        'text': block_text
                                    })
                        except Exception as ocr_err:
                            logger.warning(f"OCR layout analysis failed on page {page_num}: {ocr_err}")
                    
                    # 2. Find drawings and diagrams using erasing method
                    drawings_img = page_img.copy()
                    draw = ImageDraw.Draw(drawings_img)
                    
                    # Erase text blocks
                    for tb in text_blocks:
                        x0, y0, x1, y1 = tb['bbox']
                        pad = 8  # 8pt padding to clear stray pixels
                        px_x0 = max(0, int(x0 * zoom) - pad)
                        px_y0 = max(0, int(y0 * zoom) - pad)
                        px_x1 = min(page_img.width, int(x1 * zoom) + pad)
                        px_y1 = min(page_img.height, int(y1 * zoom) + pad)
                        draw.rectangle([px_x0, px_y0, px_x1, px_y1], fill=(255, 255, 255))
                    
                    # Convert drawings_img to grayscale and detect connected component bounding boxes
                    gray_drawings = drawings_img.convert('L')
                    
                    grid_scale = 8
                    grid_w = gray_drawings.width // grid_scale
                    grid_h = gray_drawings.height // grid_scale
                    
                    grid = []
                    for gy in range(grid_h):
                        row = []
                        for gx in range(grid_w):
                            cell_content = False
                            for dy in range(grid_scale):
                                for dx in range(grid_scale):
                                    px = gray_drawings.getpixel((gx * grid_scale + dx, gy * grid_scale + dy))
                                    if px < 240:
                                        cell_content = True
                                        break
                                if cell_content:
                                    break
                            row.append(1 if cell_content else 0)
                        grid.append(row)
                    
                    # BFS component labeling
                    visited = [[False for _ in range(grid_w)] for _ in range(grid_h)]
                    components = []
                    
                    for gy in range(grid_h):
                        for gx in range(grid_w):
                            if grid[gy][gx] == 1 and not visited[gy][gx]:
                                comp_cells = []
                                queue = [(gx, gy)]
                                visited[gy][gx] = True
                                
                                while queue:
                                    cx, cy = queue.pop(0)
                                    comp_cells.append((cx, cy))
                                    
                                    for ndx, ndy in [(-1,0), (1,0), (0,-1), (0,1), (-1,-1), (-1,1), (1,-1), (1,1)]:
                                        nx, ny = cx + ndx, cy + ndy
                                        if 0 <= nx < grid_w and 0 <= ny < grid_h:
                                            if grid[ny][nx] == 1 and not visited[ny][nx]:
                                                visited[ny][nx] = True
                                                queue.append((nx, ny))
                                                
                                min_gx = min(c[0] for c in comp_cells)
                                max_gx = max(c[0] for c in comp_cells)
                                min_gy = min(c[1] for c in comp_cells)
                                max_gy = max(c[1] for c in comp_cells)
                                
                                px_to_pt = 72.0 / 150.0
                                dx0 = min_gx * grid_scale * px_to_pt
                                dy0 = min_gy * grid_scale * px_to_pt
                                dx1 = (max_gx + 1) * grid_scale * px_to_pt
                                dy1 = (max_gy + 1) * grid_scale * px_to_pt
                                
                                components.append([dx0, dy0, dx1, dy1])
                    
                    # Merge components that are close to each other (<25pt distance)
                    merged = True
                    while merged:
                        merged = False
                        for i in range(len(components)):
                            for j in range(i + 1, len(components)):
                                c1 = components[i]
                                c2 = components[j]
                                
                                x_dist = max(0, max(c1[0], c2[0]) - min(c1[2], c2[2]))
                                y_dist = max(0, max(c1[1], c2[1]) - min(c1[3], c2[3]))
                                
                                if x_dist < 25 and y_dist < 25:
                                    components[i] = [
                                        min(c1[0], c2[0]),
                                        min(c1[1], c2[1]),
                                        max(c1[2], c2[2]),
                                        max(c1[3], c2[3])
                                    ]
                                    components.pop(j)
                                    merged = True
                                    break
                            if merged:
                                break
                    
                    # 3. Crop valid diagrams from original page image
                    diagrams = []
                    for idx, comp in enumerate(components):
                        dx0, dy0, dx1, dy1 = comp
                        d_w = dx1 - dx0
                        d_h = dy1 - dy0
                        
                        # Filter out noise and full page frames
                        if d_w < 15 or d_h < 15:
                            continue
                        if d_w > page_width * 0.95 and d_h > page_height * 0.95:
                            continue
                            
                        # Crop with small padding
                        crop_x0 = max(0, int(dx0 * zoom) - 4)
                        crop_y0 = max(0, int(dy0 * zoom) - 4)
                        crop_x1 = min(page_img.width, int(dx1 * zoom) + 4)
                        crop_y1 = min(page_img.height, int(dy1 * zoom) + 4)
                        
                        cropped_img = page_img.crop((crop_x0, crop_y0, crop_x1, crop_y1))
                        
                        temp_img_path = os.path.join(
                            self.output_path.parent,
                            f".diag_{self.pdf_path.stem}_{page_num}_{idx}.png"
                        )
                        cropped_img.save(temp_img_path)
                        temp_images.append(temp_img_path)
                        
                        diagrams.append({
                            'type': 'diagram',
                            'bbox': (dx0, dy0, dx1, dy1),
                            'path': temp_img_path
                        })
                    
                    # 4. Sort blocks and diagrams in reading order
                    merged_elements = list(text_blocks)
                    diagrams.sort(key=lambda d: d['bbox'][1])  # Sort by top coordinate
                    
                    for diag in diagrams:
                        d_x0, d_y0, d_x1, d_y1 = diag['bbox']
                        insert_idx = 0
                        for tb in text_blocks:
                            tb_x0, tb_y0, tb_x1, tb_y1 = tb['bbox']
                            
                            is_before = False
                            if tb_y1 <= d_y0 + 5:
                                is_before = True
                            elif tb_y0 < d_y1 and tb_y1 > d_y0:
                                if tb_x1 <= d_x0 + 5:
                                    is_before = True
                                    
                            if is_before:
                                insert_idx += 1
                                
                        text_count = 0
                        actual_insert_idx = 0
                        for idx, elem in enumerate(merged_elements):
                            if elem['type'] == 'text':
                                text_count += 1
                                if text_count > insert_idx:
                                    actual_insert_idx = idx
                                    break
                        else:
                            actual_insert_idx = len(merged_elements)
                            
                        merged_elements.insert(actual_insert_idx, diag)
                    
                    # 5. Write elements to document
                    p_header = doc.add_paragraph()
                    p_header.paragraph_format.space_after = Pt(6)
                    run = p_header.add_run(f"--- Page {page_num + 1} ---")
                    run.bold = True
                    
                    for elem in merged_elements:
                        if elem['type'] == 'text':
                            cleaned_text = " ".join(elem['text'].split())
                            if cleaned_text:
                                cleaned_text = clean_ocr_text(cleaned_text)
                                p_text = doc.add_paragraph(cleaned_text)
                                p_text.paragraph_format.space_before = Pt(2)
                                p_text.paragraph_format.space_after = Pt(4)
                                p_text.paragraph_format.line_spacing = 1.15
                                total_text_chars += len(cleaned_text)
                        elif elem['type'] == 'diagram':
                            try:
                                p_img = doc.add_paragraph()
                                p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                                p_img.paragraph_format.space_before = Pt(6)
                                p_img.paragraph_format.space_after = Pt(6)
                                run = p_img.add_run()
                                
                                d_w_pt = elem['bbox'][2] - elem['bbox'][0]
                                d_w_in = d_w_pt / 72.0
                                img_width = min(6.0, max(1.5, d_w_in))
                                
                                run.add_picture(elem['path'], width=Inches(img_width))
                            except Exception as embed_err:
                                logger.warning(f"Could not embed diagram: {embed_err}")
                    
                    if page_num < total_pages - 1:
                        doc.add_page_break()
                        
                doc.save(str(self.output_path))
                logger.info(f"Flowing layout conversion succeeded: {total_pages} pages, {total_text_chars} chars")
                return True
                
            finally:
                pdf.close()
                for img_path in temp_images:
                    try:
                        if os.path.exists(img_path):
                            os.remove(img_path)
                    except Exception as rm_err:
                        logger.warning(f"Could not remove temp image {img_path}: {rm_err}")
                        
        except Exception as e:
            logger.error(f"Error in flowing layout conversion: {str(e)}")
            return False
    
    def _try_pdf2docx(self) -> bool:
        """Convert using pdf2docx - for text-based PDFs, with embedded image extraction"""
        try:
            from pdf2docx import Converter
            cv = Converter(str(self.pdf_path))
            cv.convert(str(self.output_path))
            cv.close()
            
            if self.output_path.exists() and self._count_text_chars() > 50:
                # Also extract any embedded images that pdf2docx may have missed
                self._extract_embedded_images()
                logger.info(f"pdf2docx: {self._count_text_chars()} editable chars")
                return True
            
            if self.output_path.exists():
                self.output_path.unlink()
            return False
        except Exception as e:
            logger.warning(f"pdf2docx failed: {str(e)}")
            return False
    
    def _extract_embedded_images(self) -> None:
        """Extract any embedded images from PDF and add them to the Word document"""
        try:
            import fitz
            from docx import Document
            from docx.shared import Inches, Pt
            
            pdf = fitz.open(str(self.pdf_path))
            doc = Document(str(self.output_path))
            
            for page_num in range(len(pdf)):
                page = pdf[page_num]
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    try:
                        xref = img[0]
                        pix = fitz.Pixmap(fitz.csRGB, fitz.Pixmap(pdf, xref))
                        if pix.n > 4:
                            pix = fitz.Pixmap(fitz.csRGB, pix)
                        
                        temp_img_path = os.path.join(
                            self.output_path.parent,
                            f".embedded_{self.pdf_path.stem}_{page_num}_{img_index}.png"
                        )
                        pix.save(temp_img_path)
                        
                        p_img = doc.add_paragraph()
                        p_img.paragraph_format.space_after = Pt(6)
                        run = p_img.add_run()
                        run.add_picture(temp_img_path, width=Inches(4.5))
                        
                        os.remove(temp_img_path)
                    except Exception as img_err:
                        logger.warning(f"Could not extract embedded image: {img_err}")
            
            doc.save(str(self.output_path))
            pdf.close()
        except Exception as e:
            logger.warning(f"Embedded image extraction failed: {str(e)}")
    
    def _try_hybrid_image_plus_text(self) -> bool:
        """
        FULLY EDITABLE approach for scanned/image PDFs:
        
        For EACH page:
        1. Extract all images/diagrams from the page as inline images
        2. OCR extract ALL text at high DPI for full editability
        3. Combine both: editable text with diagrams embedded inline where they belong
        
        The result is a Word document where:
        - ALL text is fully editable (not just sections) - you can select, copy, modify any text
        - Diagrams, charts, pictures are preserved as inline images
        """
        try:
            import fitz
            from PIL import Image, ImageEnhance, ImageFilter
            import pytesseract
            from docx import Document
            from docx.shared import Inches, Pt, Cm
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            
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
                logger.warning("Tesseract not available for hybrid mode")
                return False
            
            pdf = fitz.open(str(self.pdf_path))
            total_pages = len(pdf)
            
            logger.info(f"Fully editable conversion: {total_pages} pages")
            
            doc = Document()
            style = doc.styles['Normal']
            style.font.name = 'Calibri'
            style.font.size = Pt(11)
            
            for section in doc.sections:
                section.top_margin = Cm(2.0)
                section.bottom_margin = Cm(2.0)
                section.left_margin = Cm(2.5)
                section.right_margin = Cm(2.5)
            
            total_text_chars = 0
            temp_images = []
            
            try:
                for page_num in range(total_pages):
                    page = pdf[page_num]
                    
                    # =========================================================
                    # PART 1: Extract all images/diagrams from the page
                    page_images = []
                    image_list = page.get_images()
                    
                    for img_index, img in enumerate(image_list):
                        try:
                            xref = img[0]
                            pix = fitz.Pixmap(fitz.csRGB, fitz.Pixmap(pdf, xref))
                            if pix.n > 4:
                                pix = fitz.Pixmap(fitz.csRGB, pix)
                            
                            temp_img_path = os.path.join(
                                self.output_path.parent,
                                f".page_img_{self.pdf_path.stem}_{page_num}_{img_index}.png"
                            )
                            pix.save(temp_img_path)
                            page_images.append(temp_img_path)
                            temp_images.append(temp_img_path)
                        except Exception as img_err:
                            logger.warning(f"Could not extract image {img_index} from page {page_num}: {img_err}")
                    
                    # =========================================================
                    # PART 2: OCR extract ALL text at high DPI for full editability
                    # =========================================================
                    zoom = 4.0
                    mat = fitz.Matrix(zoom, zoom)
                    pix_ocr = page.get_pixmap(matrix=mat, dpi=300, alpha=False)
                    
                    pil_img = Image.frombytes("RGB", [pix_ocr.width, pix_ocr.height], pix_ocr.samples)
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
                    
                    # Add page header
                    p_header = doc.add_paragraph()
                    p_header.paragraph_format.space_after = Pt(6)
                    run = p_header.add_run(f"--- Page {page_num + 1} ---")
                    run.bold = True
                    
                    # PART 3: Add extracted diagrams as inline images
                    if page_images:
                        for img_path in page_images:
                            try:
                                p_img = doc.add_paragraph()
                                p_img.paragraph_format.space_after = Pt(6)
                                run = p_img.add_run()
                                run.add_picture(img_path, width=Inches(4.5))
                            except Exception as embed_err:
                                logger.warning(f"Could not embed image: {embed_err}")
                    
                    # PART 4: Add ALL OCR-extracted text (fully editable)
                    if page_text and page_text.strip():
                        for para_text in page_text.split('\n'):
                            if para_text.strip():
                                cleaned_para = clean_ocr_text(para_text.strip())
                                p_text = doc.add_paragraph(cleaned_para)
                                p_text.paragraph_format.space_before = Pt(1)
                                p_text.paragraph_format.space_after = Pt(1)
                                p_text.paragraph_format.line_spacing = 1.15
                        total_text_chars += len(page_text)
                    else:
                        doc.add_paragraph("[No text detected on this page]")
                    
                    if page_num < total_pages - 1:
                        doc.add_page_break()
                
                doc.save(str(self.output_path))
                
                logger.info(f"Fully editable output: {total_pages}p pages with {total_text_chars} editable chars")
                return True
            
            finally:
                for img_path in temp_images:
                    try:
                        if os.path.exists(img_path):
                            os.remove(img_path)
                    except:
                        pass
        
        except Exception as e:
            logger.warning(f"Fully editable hybrid conversion failed: {str(e)}")
            return False
    
    def _fallback_page_images(self) -> bool:
        """Last resort: page images with OCR text for full editability"""
        try:
            import fitz
            from PIL import Image, ImageEnhance
            import pytesseract
            from docx import Document
            from docx.shared import Inches, Pt, Cm
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            
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
                return self._images_only_fallback()
            
            pdf = fitz.open(str(self.pdf_path))
            total_pages = len(pdf)
            
            doc = Document()
            for section in doc.sections:
                section.top_margin = Cm(1.5)
                section.bottom_margin = Cm(1.5)
                section.left_margin = Cm(1.5)
                section.right_margin = Cm(1.5)
            
            temp_paths = []
            total_text_chars = 0
            
            try:
                for page_num in range(total_pages):
                    page = pdf[page_num]
                    zoom = 2.0
                    mat = fitz.Matrix(zoom, zoom)
                    pix = page.get_pixmap(matrix=mat, alpha=False)
                    
                    temp_path = os.path.join(
                        self.output_path.parent,
                        f".fallback_page_{self.pdf_path.stem}_{page_num}.png"
                    )
                    pix.save(temp_path)
                    temp_paths.append(temp_path)
                    
                    p = doc.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    run = p.add_run()
                    run.add_picture(temp_path, width=Inches(6.5))
                    
                    pix_ocr = page.get_pixmap(dpi=200, alpha=False)
                    pil_img = Image.frombytes("RGB", [pix_ocr.width, pix_ocr.height], pix_ocr.samples)
                    pil_img = pil_img.convert('L')
                    enhancer = ImageEnhance.Contrast(pil_img)
                    pil_img = enhancer.enhance(1.5)
                    
                    page_text = pytesseract.image_to_string(pil_img, config=r'--oem 3 --psm 6')
                    
                    if page_text and page_text.strip():
                        cleaned_para = clean_ocr_text(page_text.strip())
                        p_text = doc.add_paragraph(cleaned_para)
                        p_text.paragraph_format.space_before = Pt(6)
                        total_text_chars += len(page_text)
                    
                    if page_num < total_pages - 1:
                        doc.add_page_break()
                
                doc.save(str(self.output_path))
                logger.info(f"Fallback with OCR: {total_pages}p images + {total_text_chars} editable chars")
                return True
            finally:
                pdf.close()
                for path in temp_paths:
                    try:
                        if os.path.exists(path):
                            os.remove(path)
                    except:
                        pass
        except Exception as e:
            logger.error(f"Fallback failed: {str(e)}")
            return False
    
    def _images_only_fallback(self) -> bool:
        """Pure page images fallback when OCR is unavailable"""
        try:
            import fitz
            from docx import Document
            from docx.shared import Inches, Pt, Cm
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            
            pdf = fitz.open(str(self.pdf_path))
            total_pages = len(pdf)
            
            doc = Document()
            for section in doc.sections:
                section.top_margin = Cm(1.5)
                section.bottom_margin = Cm(1.5)
                section.left_margin = Cm(1.5)
                section.right_margin = Cm(1.5)
            
            temp_paths = []
            
            try:
                for page_num in range(total_pages):
                    page = pdf[page_num]
                    zoom = 2.0
                    mat = fitz.Matrix(zoom, zoom)
                    pix = page.get_pixmap(matrix=mat, alpha=False)
                    
                    temp_path = os.path.join(
                        self.output_path.parent,
                        f".fallback_page_{self.pdf_path.stem}_{page_num}.png"
                    )
                    pix.save(temp_path)
                    temp_paths.append(temp_path)
                    
                    p = doc.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    run = p.add_run()
                    run.add_picture(temp_path, width=Inches(6.5))
                    
                    if page_num < total_pages - 1:
                        doc.add_page_break()
                
                doc.save(str(self.output_path))
                logger.info(f"Images-only fallback: {total_pages}p pages")
                return True
            finally:
                pdf.close()
                for path in temp_paths:
                    try:
                        if os.path.exists(path):
                            os.remove(path)
                    except:
                        pass
        except Exception as e:
            logger.error(f"Images-only fallback failed: {str(e)}")
            return False
    
    def _count_text_chars(self) -> int:
        try:
            from docx import Document
            doc = Document(str(self.output_path))
            return sum(len(p.text) for p in doc.paragraphs)
        except:
            return 0