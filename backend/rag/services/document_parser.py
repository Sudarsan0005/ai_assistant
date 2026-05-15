"""
Document Parser with Vision Support
Handles PDF, DOCX, images, tables, and other document types
"""
import io
import os
import re
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
import logging

import PyPDF2
import pdfplumber
from docx import Document
from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ParsedSection:
    """Represents a parsed section from a document"""
    text: str
    doc_type: str  # text, table, image, title, etc.
    page_number: int
    position: Dict[str, float]  # x0, y0, x1, y1
    metadata: Dict[str, Any]
    image_id: Optional[str] = None


class DocumentParser:
    """Multi-format document parser with vision capabilities"""
    
    def __init__(self, enable_vision: bool = True, ocr_lang: str = "en"):
        self.enable_vision = enable_vision
        self.ocr_lang = ocr_lang
        
        if enable_vision:
            try:
                from paddleocr import PaddleOCR
                self.ocr_engine = PaddleOCR(
                    use_angle_cls=True,
                    lang=ocr_lang,
                    show_log=False
                )
                logger.info("PaddleOCR initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize OCR: {e}")
                self.ocr_engine = None
    
    def parse(self, file_path: str, filename: str) -> List[ParsedSection]:
        """Parse document based on file extension"""
        ext = Path(filename).suffix.lower()
        
        parsers = {
            '.pdf': self._parse_pdf,
            '.docx': self._parse_docx,
            '.txt': self._parse_txt,
            '.md': self._parse_markdown,
            '.png': self._parse_image,
            '.jpg': self._parse_image,
            '.jpeg': self._parse_image,
        }
        
        parser = parsers.get(ext)
        if not parser:
            raise ValueError(f"Unsupported file format: {ext}")
        
        return parser(file_path)
    
    def _parse_pdf(self, file_path: str) -> List[ParsedSection]:
        """Parse PDF with layout analysis and table extraction"""
        sections = []
        
        try:
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    # Extract text with positions
                    words = page.extract_words(
                        x_tolerance=3,
                        y_tolerance=3,
                        keep_blank_chars=False
                    )
                    
                    # Group words into sections by layout
                    text_sections = self._group_words_by_layout(words, page_num)
                    sections.extend(text_sections)
                    
                    # Extract tables
                    tables = page.extract_tables()
                    for table_idx, table in enumerate(tables):
                        if table:
                            table_text = self._format_table(table)
                            # Get table bounding box
                            bbox = self._get_table_bbox(page, table)
                            
                            sections.append(ParsedSection(
                                text=table_text,
                                doc_type="table",
                                page_number=page_num,
                                position=bbox,
                                metadata={"table_index": table_idx}
                            ))
                    
                    # Extract images if vision is enabled
                    if self.enable_vision:
                        images = self._extract_pdf_images(page, page_num)
                        sections.extend(images)
        
        except Exception as e:
            logger.error(f"Error parsing PDF: {e}")
            # Fallback to basic text extraction
            sections = self._parse_pdf_fallback(file_path)
        
        return sections
    
    def _group_words_by_layout(
        self, 
        words: List[Dict], 
        page_num: int
    ) -> List[ParsedSection]:
        """Group words into logical sections based on layout"""
        if not words:
            return []
        
        sections = []
        current_section = []
        prev_y = None
        
        for word in words:
            y_pos = word['top']
            
            # New section if significant vertical gap
            if prev_y and abs(y_pos - prev_y) > 10:
                if current_section:
                    text = ' '.join([w['text'] for w in current_section])
                    bbox = self._calculate_bbox(current_section)
                    
                    # Classify section type
                    doc_type = self._classify_text_type(text)
                    
                    sections.append(ParsedSection(
                        text=text,
                        doc_type=doc_type,
                        page_number=page_num,
                        position=bbox,
                        metadata={}
                    ))
                    current_section = []
            
            current_section.append(word)
            prev_y = y_pos + word['height']
        
        # Add final section
        if current_section:
            text = ' '.join([w['text'] for w in current_section])
            bbox = self._calculate_bbox(current_section)
            sections.append(ParsedSection(
                text=text,
                doc_type=self._classify_text_type(text),
                page_number=page_num,
                position=bbox,
                metadata={}
            ))
        
        return sections
    
    def _classify_text_type(self, text: str) -> str:
        """Classify text as title, header, body, etc."""
        text_clean = text.strip()
        
        # Title detection (short, all caps, or starts with chapter/section)
        if len(text_clean) < 100 and (
            text_clean.isupper() or
            re.match(r'^(Chapter|Section|Part)\s+\d+', text_clean, re.I)
        ):
            return "title"
        
        # Header/Footer detection
        if len(text_clean) < 50 and any(
            keyword in text_clean.lower() 
            for keyword in ['page', 'copyright', '©']
        ):
            return "header"
        
        return "text"
    
    def _calculate_bbox(self, words: List[Dict]) -> Dict[str, float]:
        """Calculate bounding box from words"""
        if not words:
            return {"x0": 0, "y0": 0, "x1": 0, "y1": 0}
        
        x0 = min(w['x0'] for w in words)
        y0 = min(w['top'] for w in words)
        x1 = max(w['x1'] for w in words)
        y1 = max(w['bottom'] for w in words)
        
        return {"x0": x0, "y0": y0, "x1": x1, "y1": y1}
    
    def _format_table(self, table: List[List]) -> str:
        """Format table as markdown"""
        if not table:
            return ""
        
        # Clean empty rows
        table = [row for row in table if any(cell for cell in row)]
        
        if not table:
            return ""
        
        # Create markdown table
        lines = []
        for i, row in enumerate(table):
            row_clean = [str(cell or '').strip() for cell in row]
            lines.append('| ' + ' | '.join(row_clean) + ' |')
            
            # Add separator after header
            if i == 0:
                lines.append('| ' + ' | '.join(['---'] * len(row)) + ' |')
        
        return '\n'.join(lines)
    
    def _get_table_bbox(self, page, table) -> Dict[str, float]:
        """Get table bounding box (approximation)"""
        # Use page dimensions as fallback
        return {
            "x0": 0,
            "y0": 0,
            "x1": page.width,
            "y1": page.height
        }
    
    def _extract_pdf_images(
        self, 
        page, 
        page_num: int
    ) -> List[ParsedSection]:
        """Extract and OCR images from PDF page"""
        sections = []
        
        try:
            images = page.images
            for img_idx, img in enumerate(images):
                if self.ocr_engine:
                    # Extract image and perform OCR
                    # Note: Simplified - in production, you'd extract actual image bytes
                    bbox = {
                        "x0": img.get('x0', 0),
                        "y0": img.get('top', 0),
                        "x1": img.get('x1', 0),
                        "y1": img.get('bottom', 0)
                    }
                    
                    sections.append(ParsedSection(
                        text="[Image content - OCR would be performed here]",
                        doc_type="image",
                        page_number=page_num,
                        position=bbox,
                        metadata={"image_index": img_idx},
                        image_id=f"img_{page_num}_{img_idx}"
                    ))
        except Exception as e:
            logger.warning(f"Error extracting images: {e}")
        
        return sections
    
    def _parse_pdf_fallback(self, file_path: str) -> List[ParsedSection]:
        """Fallback PDF parser using PyPDF2"""
        sections = []
        
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            for page_num, page in enumerate(pdf_reader.pages, 1):
                text = page.extract_text()
                
                if text.strip():
                    sections.append(ParsedSection(
                        text=text,
                        doc_type="text",
                        page_number=page_num,
                        position={"x0": 0, "y0": 0, "x1": 0, "y1": 0},
                        metadata={}
                    ))
        
        return sections
    
    def _parse_docx(self, file_path: str) -> List[ParsedSection]:
        """Parse DOCX file"""
        sections = []
        doc = Document(file_path)
        
        for para_idx, paragraph in enumerate(doc.paragraphs):
            if not paragraph.text.strip():
                continue
            
            # Detect if it's a heading
            doc_type = "title" if paragraph.style.name.startswith('Heading') else "text"
            
            sections.append(ParsedSection(
                text=paragraph.text,
                doc_type=doc_type,
                page_number=para_idx // 20 + 1,  # Approximate pages
                position={"x0": 0, "y0": 0, "x1": 0, "y1": 0},
                metadata={"style": paragraph.style.name}
            ))
        
        # Parse tables
        for table_idx, table in enumerate(doc.tables):
            table_text = self._parse_docx_table(table)
            sections.append(ParsedSection(
                text=table_text,
                doc_type="table",
                page_number=table_idx // 5 + 1,
                position={"x0": 0, "y0": 0, "x1": 0, "y1": 0},
                metadata={"table_index": table_idx}
            ))
        
        return sections
    
    def _parse_docx_table(self, table) -> str:
        """Parse DOCX table to markdown"""
        rows = []
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            rows.append(cells)
        return self._format_table(rows)
    
    def _parse_txt(self, file_path: str) -> List[ParsedSection]:
        """Parse plain text file"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        
        # Split into paragraphs
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        sections = []
        for idx, para in enumerate(paragraphs):
            sections.append(ParsedSection(
                text=para,
                doc_type="text",
                page_number=idx // 10 + 1,
                position={"x0": 0, "y0": 0, "x1": 0, "y1": 0},
                metadata={}
            ))
        
        return sections
    
    def _parse_markdown(self, file_path: str) -> List[ParsedSection]:
        """Parse Markdown file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        sections = []
        current_text = []
        current_type = "text"
        
        for line in content.split('\n'):
            # Detect headers
            if line.startswith('#'):
                if current_text:
                    sections.append(ParsedSection(
                        text='\n'.join(current_text),
                        doc_type=current_type,
                        page_number=len(sections) // 10 + 1,
                        position={"x0": 0, "y0": 0, "x1": 0, "y1": 0},
                        metadata={}
                    ))
                    current_text = []
                current_type = "title"
                current_text.append(line.lstrip('#').strip())
            else:
                if current_type == "title" and current_text:
                    sections.append(ParsedSection(
                        text='\n'.join(current_text),
                        doc_type=current_type,
                        page_number=len(sections) // 10 + 1,
                        position={"x0": 0, "y0": 0, "x1": 0, "y1": 0},
                        metadata={}
                    ))
                    current_text = []
                    current_type = "text"
                
                if line.strip():
                    current_text.append(line)
        
        if current_text:
            sections.append(ParsedSection(
                text='\n'.join(current_text),
                doc_type=current_type,
                page_number=len(sections) // 10 + 1,
                position={"x0": 0, "y0": 0, "x1": 0, "y1": 0},
                metadata={}
            ))
        
        return sections
    
    def _parse_image(self, file_path: str) -> List[ParsedSection]:
        """Parse image file with OCR"""
        if not self.ocr_engine:
            return [ParsedSection(
                text="[Image - OCR not available]",
                doc_type="image",
                page_number=1,
                position={"x0": 0, "y0": 0, "x1": 0, "y1": 0},
                metadata={},
                image_id="img_0"
            )]
        
        try:
            result = self.ocr_engine.ocr(file_path, cls=True)
            
            if not result or not result[0]:
                return []
            
            # Extract text from OCR results
            texts = []
            for line in result[0]:
                if line[1][0]:  # Check if text exists
                    texts.append(line[1][0])
            
            combined_text = '\n'.join(texts)
            
            return [ParsedSection(
                text=combined_text,
                doc_type="image",
                page_number=1,
                position={"x0": 0, "y0": 0, "x1": 0, "y1": 0},
                metadata={"ocr_confidence": "high"},
                image_id="img_0"
            )]
        
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return []
