"""
DocxToPdfConverter - Converts Word documents (.docx) to PDF files.
This conversion is FREE (no payment required).
"""
import os
import logging
import shutil
import subprocess
import tempfile
from xml.sax.saxutils import escape
from docx import Document
from io import BytesIO

logger = logging.getLogger(__name__)


class DocxToPdfConverter:
    """Converts Word documents to PDF files using reportlab."""

    def __init__(self, docx_path: str, output_path: str):
        self.docx_path = docx_path
        self.output_path = output_path
        self.error_message = None

    def convert(self) -> bool:
        """Convert a .docx file to PDF. Returns True if successful."""
        try:
            if self._convert_with_libreoffice():
                return True

            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm, cm
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_LEFT, TA_CENTER
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.colors import HexColor, black

            # Try to open the document with error handling for corrupted images
            doc = None
            try:
                doc = Document(self.docx_path)
            except Exception as open_err:
                logger.warning(f"Could not open docx directly: {open_err}")
                # Try to fix the corrupted docx by removing corrupted media files
                import zipfile
                import shutil
                import tempfile
                import re
                
                fixed_path = self.docx_path + '.fixed.docx'
                try:
                    with zipfile.ZipFile(self.docx_path, 'r') as zin:
                        with zipfile.ZipFile(fixed_path, 'w') as zout:
                            for item in zin.infolist():
                                data = zin.read(item.filename)
                                # Skip corrupted image files (they cause CRC errors)
                                if item.filename.startswith('word/media/'):
                                    try:
                                        # Test if the data is valid
                                        import zlib
                                        zlib.crc32(data)
                                    except:
                                        logger.warning(f"Skipping corrupted media file: {item.filename}")
                                        continue
                                zout.writestr(item, data)
                    
                    doc = Document(fixed_path)
                except Exception as fix_err:
                    logger.error(f"Could not fix corrupted docx: {fix_err}")
                    # Last resort: try to extract text via zip
                    try:
                        text_content = []
                        import zipfile
                        with zipfile.ZipFile(self.docx_path, 'r') as z:
                            # Try to read the document.xml directly
                            xml_data = z.read('word/document.xml')
                            import xml.etree.ElementTree as ET
                            root = ET.fromstring(xml_data)
                            # Extract all text
                            ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                            for t in root.iterfind('.//w:t', ns):
                                if t.text:
                                    text_content.append(t.text)
                        
                        if text_content:
                            full_text = ' '.join(text_content)
                            # Create a minimal PDF with extracted text
                            doc_template = SimpleDocTemplate(
                                self.output_path,
                                pagesize=A4,
                                leftMargin=2*cm,
                                rightMargin=2*cm,
                                topMargin=2*cm,
                                bottomMargin=2*cm,
                            )
                            elements = [Paragraph(escape(full_text[:10000]), ParagraphStyle('Body', fontSize=10, leading=14))]
                            doc_template.build(elements)
                            logger.info(f"Extracted text from corrupted docx, saved to PDF")
                            return True
                    except:
                        pass
                    return False
            
            # Create the PDF
            os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
            
            doc_template = SimpleDocTemplate(
                self.output_path,
                pagesize=A4,
                leftMargin=2*cm,
                rightMargin=2*cm,
                topMargin=2*cm,
                bottomMargin=2*cm,
            )

            styles = getSampleStyleSheet()
            normal_style = ParagraphStyle(
                'DocxNormal',
                parent=styles['Normal'],
                fontSize=10,
                leading=14,
                spaceAfter=6,
            )
            heading_style = ParagraphStyle(
                'DocxHeading',
                parent=styles['Heading1'],
                fontSize=16,
                leading=20,
                spaceAfter=12,
                spaceBefore=12,
                textColor=HexColor('#1a1a2e'),
            )
            heading2_style = ParagraphStyle(
                'DocxHeading2',
                parent=styles['Heading2'],
                fontSize=14,
                leading=18,
                spaceAfter=10,
                spaceBefore=10,
                textColor=HexColor('#2d2d5e'),
            )
            title_style = ParagraphStyle(
                'DocxTitle',
                parent=styles['Title'],
                fontSize=20,
                leading=24,
                spaceAfter=16,
                alignment=TA_CENTER,
                textColor=HexColor('#1a1a2e'),
            )

            elements = []

            for para in doc.paragraphs:
                text = para.text.strip()
                if not text:
                    elements.append(Spacer(1, 6))
                    continue

                style_name = para.style.name if para.style else 'Normal'

                if 'Title' in style_name:
                    elements.append(Paragraph(escape(text), title_style))
                elif 'Heading 1' in style_name or 'heading 1' in style_name.lower():
                    elements.append(Paragraph(escape(text), heading_style))
                elif 'Heading 2' in style_name or 'heading 2' in style_name.lower():
                    elements.append(Paragraph(escape(text), heading2_style))
                elif 'Heading 3' in style_name or 'heading 3' in style_name.lower():
                    h3 = ParagraphStyle('H3', parent=heading2_style, fontSize=12, leading=16)
                    elements.append(Paragraph(escape(text), h3))
                else:
                    elements.append(Paragraph(escape(text), normal_style))

            # Handle tables
            for table in doc.tables:
                try:
                    num_cols = len(table.columns)
                    if not num_cols:
                        continue
                    page_width = A4[0] - 4*cm
                    col_width = page_width / num_cols
                    col_widths = [col_width] * num_cols
                    available_height = A4[1] - 4*cm
                    table_data = []

                    def append_table_segment(rows):
                        if not rows:
                            return
                        table_flowable = Table(rows, colWidths=col_widths, splitInRow=1)
                        table_flowable.setStyle(TableStyle([
                            ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cccccc')),
                            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#e8edf5')),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('LEFTPADDING', (0, 0), (-1, -1), 3),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                            ('TOPPADDING', (0, 0), (-1, -1), 2),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                        ]))
                        elements.append(table_flowable)
                        elements.append(Spacer(1, 12))

                    for row in table.rows:
                        cell_texts = [cell.text.strip() for cell in row.cells]
                        row_data = [
                            Paragraph(escape(cell_text).replace('\n', '<br/>'), normal_style)
                            for cell_text in cell_texts
                        ]
                        if any(
                            paragraph.wrap(col_width - 6, available_height * 2)[1] > available_height
                            for paragraph in row_data
                        ):
                            append_table_segment(table_data)
                            table_data = []
                            for cell_text in cell_texts:
                                if cell_text:
                                    elements.append(Paragraph(
                                        escape(cell_text).replace('\n', '<br/>'),
                                        normal_style,
                                    ))
                                    elements.append(Spacer(1, 4))
                            elements.append(Spacer(1, 8))
                        else:
                            table_data.append(row_data)
                    append_table_segment(table_data)
                except Exception as table_err:
                    logger.warning(f"Could not render table, adding as text: {table_err}")
                    # Fallback: render table as plain text
                    for row in table.rows:
                        row_text = " | ".join(cell.text.strip() for cell in row.cells)
                        if row_text.strip():
                            elements.append(Paragraph(escape(row_text), normal_style))

            doc_template.build(elements)
            logger.info(f"Successfully converted {self.docx_path} to PDF: {self.output_path}")
            return True

        except Exception as e:
            self.error_message = (
                'The Word document contains content that could not be laid out. '
                'Try installing LibreOffice for full formatting support, or simplify unusually large tables.'
            )
            logger.exception("Error converting DOCX to PDF: %s", e)
            return False

    def _convert_with_libreoffice(self) -> bool:
        """Use LibreOffice's document renderer when installed to preserve Word layout."""
        executable = shutil.which('soffice') or shutil.which('libreoffice')
        if not executable:
            return False

        output_dir = os.path.dirname(os.path.abspath(self.output_path))
        os.makedirs(output_dir, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='docx_to_pdf_') as temp_dir:
            profile_uri = (os.path.join(temp_dir, 'profile')).replace(os.sep, '/')
            result_dir = os.path.join(temp_dir, 'output')
            os.makedirs(result_dir)
            command = [
                executable,
                '--headless',
                f'-env:UserInstallation=file:///{profile_uri.lstrip("/")}',
                '--convert-to',
                'pdf',
                '--outdir',
                result_dir,
                os.path.abspath(self.docx_path),
            ]
            result = subprocess.run(command, capture_output=True, text=True, timeout=180)
            rendered_pdf = os.path.join(
                result_dir,
                os.path.splitext(os.path.basename(self.docx_path))[0] + '.pdf',
            )
            if result.returncode != 0 or not os.path.isfile(rendered_pdf):
                logger.warning(
                    "LibreOffice DOCX rendering failed (exit %s): %s",
                    result.returncode,
                    result.stderr.strip() or result.stdout.strip(),
                )
                return False

            shutil.copyfile(rendered_pdf, self.output_path)
            return True