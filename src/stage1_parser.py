"""
Stage 1: Document Parser
========================
Deterministic PDF text extraction with section detection.
Extracts text, identifies sections, and tracks page numbers.
"""

import pdfplumber
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Section:
    """Represents a detected section in the document."""
    name: str
    section_type: str  # notes, md&a, financial_statements, accounting_policies, other
    start_page: int
    end_page: int
    text: str
    tables: list = field(default_factory=list)


@dataclass
class ParsedDocument:
    """Complete parsed document structure."""
    filename: str
    total_pages: int
    sections: list[Section]
    full_text: str
    pages: list[dict]  # [{page_num, text, tables}]
    tables: list[dict]  # [{page_num, data}]


class DocumentParser:
    """
    Stage 1: Parse PDF documents into structured sections.
    """
    
    # Section detection patterns
    SECTION_PATTERNS = {
        'notes': [
            r'notes?\s+to\s+(consolidated\s+)?financial\s+statements',
            r'notes?\s+to\s+the\s+(consolidated\s+)?financial\s+statements',
            r'^note\s+\d+[\.\:\s]',
            r'footnotes?\s+to',
        ],
        'accounting_policies': [
            r'(significant\s+)?accounting\s+policies',
            r'summary\s+of\s+significant\s+accounting\s+policies',
            r'basis\s+of\s+presentation',
        ],
        'md&a': [
            r"management'?s?\s+discussion\s+and\s+analysis",
            r'md&a',
            r'results\s+of\s+operations',
        ],
        'financial_statements': [
            r'consolidated\s+statements?\s+of\s+(operations?|income)',
            r'consolidated\s+balance\s+sheets?',
            r'consolidated\s+statements?\s+of\s+cash\s+flows?',
            r'consolidated\s+statements?\s+of\s+(stockholders?|shareholders?)',
        ],
        'cover': [
            r'form\s+10-k',
            r'annual\s+report',
            r'securities\s+and\s+exchange\s+commission',
        ],
    }
    
    # Note-specific patterns for sub-section detection
    NOTE_PATTERNS = [
        r'^note\s+(\d+)[\.\:\s\-]+(.+?)(?:\n|$)',
        r'(\d+)\.\s+([A-Z][A-Za-z\s,&]+?)(?:\n|$)',
    ]
    
    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        
        self.pages: list[dict] = []
        self.tables: list[dict] = []
        self.sections: list[Section] = []
        self.full_text = ""
        
    def parse(self) -> ParsedDocument:
        """
        Parse the PDF and return structured document.
        """
        print(f"[Stage 1] Parsing: {self.pdf_path.name}")
        
        # Extract all pages
        self._extract_pages()
        
        # Detect sections
        self._detect_sections()
        
        # Build parsed document
        doc = ParsedDocument(
            filename=self.pdf_path.name,
            total_pages=len(self.pages),
            sections=self.sections,
            full_text=self.full_text,
            pages=self.pages,
            tables=self.tables
        )
        
        print(f"[Stage 1] Extracted {len(self.pages)} pages, {len(self.sections)} sections, {len(self.tables)} tables")
        
        return doc
    
    def _extract_pages(self):
        """Extract text and tables from all pages."""
        with pdfplumber.open(self.pdf_path) as pdf:
            total = len(pdf.pages)
            
            for i, page in enumerate(pdf.pages):
                page_num = i + 1
                
                if page_num % 25 == 0:
                    print(f"  Processing page {page_num}/{total}...")
                
                # Extract text
                text = page.extract_text() or ""
                
                # Extract tables
                page_tables = []
                try:
                    tables = page.extract_tables()
                    for table in tables:
                        if table and len(table) > 1:
                            page_tables.append(table)
                            self.tables.append({
                                'page_num': page_num,
                                'data': table
                            })
                except Exception:
                    pass  # Skip problematic tables
                
                self.pages.append({
                    'page_num': page_num,
                    'text': text,
                    'tables': page_tables
                })
                
                self.full_text += f"\n\n[PAGE {page_num}]\n{text}"
    
    def _detect_sections(self):
        """Detect and classify document sections."""
        current_section = None
        current_type = 'other'
        current_start = 1
        section_text = ""
        section_tables = []
        in_notes_section = False  # Track if we're in Notes
        notes_start_page = None
        
        for page in self.pages:
            page_num = page['page_num']
            text = page['text']
            text_lower = text.lower()
            
            # Check for section boundaries
            detected_type = self._classify_page(text_lower, in_notes_section)
            
            # Check if this page TRULY starts the Notes section
            # Must have "Note 1" or "NOTE 1" indicating the actual notes content
            if not in_notes_section:
                # Look for actual Note 1 (not just TOC mention)
                if re.search(r'\bnote\s+1[\.\:\s\-]', text_lower):
                    # Verify it's not a TOC by checking for substantial text after
                    if len(text) > 1000:  # TOC pages are usually shorter
                        in_notes_section = True
                        notes_start_page = page_num
                        detected_type = 'notes'
            
            # Once in Notes, ANY page with "Note X." stays in Notes
            if in_notes_section:
                # Check for exit signals (signatures, exhibits, end markers)
                if self._is_notes_exit(text_lower, page_num):
                    in_notes_section = False
                else:
                    # Stay in notes - override any misdetection
                    detected_type = 'notes'
            
            # Also detect notes pages that may have been missed (for fragmented notes)
            if not in_notes_section and re.search(r'^note\s+\d+[\.\:\s]', text_lower, re.MULTILINE):
                # This is a notes page - check if we should be in notes
                detected_type = 'notes'
            
            # If section type changed, save previous section
            if detected_type != current_type and detected_type != 'other':
                if section_text.strip():
                    self.sections.append(Section(
                        name=self._get_section_name(current_type, section_text),
                        section_type=current_type,
                        start_page=current_start,
                        end_page=page_num - 1,
                        text=section_text,
                        tables=section_tables
                    ))
                
                current_type = detected_type
                current_start = page_num
                section_text = ""
                section_tables = []
            
            section_text += f"\n\n[PAGE {page_num}]\n{text}"
            section_tables.extend(page['tables'])
        
        # Save final section
        if section_text.strip():
            self.sections.append(Section(
                name=self._get_section_name(current_type, section_text),
                section_type=current_type,
                start_page=current_start,
                end_page=len(self.pages),
                text=section_text,
                tables=section_tables
            ))
        
        # Merge fragmented notes sections
        self._merge_notes_sections()
        
        # Enhance notes section detection
        self._detect_individual_notes()
    
    def _is_notes_exit(self, text_lower: str, page_num: int) -> bool:
        """Check if this page signals exit from Notes section."""
        exit_patterns = [
            r'signatures?\s*$',
            r'exhibit\s+index',
            r'exhibits?\s+and\s+financial',
            r'part\s+iv',
            r'power\s+of\s+attorney',
        ]
        for pattern in exit_patterns:
            if re.search(pattern, text_lower):
                return True
        return False
    
    def _merge_notes_sections(self):
        """Merge fragmented Notes sections and include embedded tables/statements."""
        notes_indices = [i for i, s in enumerate(self.sections) if s.section_type == 'notes']
        
        if len(notes_indices) == 0:
            return  # No notes found
        
        # Get the notes range
        min_start = min(self.sections[i].start_page for i in notes_indices)
        max_end = max(self.sections[i].end_page for i in notes_indices)
        
        # Also look for financial_statements sections BETWEEN notes pages
        # These are likely embedded tables within the notes
        for section in self.sections:
            if section.section_type == 'financial_statements':
                # Check if this is between notes pages or adjacent
                if min_start <= section.start_page <= max_end + 5:
                    # Check if pages contain "Note X." pattern
                    if re.search(r'note\s+\d+[\.\:]', section.text.lower()):
                        # This is actually part of notes
                        max_end = max(max_end, section.end_page)
        
        # Now merge all pages in the notes range
        merged_text = ""
        merged_tables = []
        
        for page in self.pages:
            if min_start <= page['page_num'] <= max_end:
                merged_text += f"\n\n[PAGE {page['page_num']}]\n{page['text']}"
                merged_tables.extend(page['tables'])
        
        # Create merged section
        merged_section = Section(
            name='Notes to Financial Statements',
            section_type='notes',
            start_page=min_start,
            end_page=max_end,
            text=merged_text,
            tables=merged_tables
        )
        
        # Remove old notes and embedded financial_statements sections
        self.sections = [
            s for s in self.sections 
            if not (s.section_type == 'notes' or 
                   (s.section_type == 'financial_statements' and min_start <= s.start_page <= max_end))
        ]
        self.sections.append(merged_section)
        
        # Re-sort by start page
        self.sections.sort(key=lambda s: s.start_page)
    
    def _classify_page(self, text_lower: str, in_notes_section: bool = False) -> str:
        """Classify a page into a section type."""
        # If we're in notes section and page contains "Note X.", keep it as notes
        if in_notes_section:
            if re.search(r'note\s+\d+\.', text_lower):
                return 'notes'
        
        # Priority check: "Note X." at start of line strongly indicates notes
        if re.search(r'^note\s+\d+[\.\:\s]', text_lower, re.MULTILINE):
            return 'notes'
        
        for section_type, patterns in self.SECTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    return section_type
        return 'other'
    
    def _get_section_name(self, section_type: str, text: str) -> str:
        """Generate a descriptive name for a section."""
        type_names = {
            'notes': 'Notes to Financial Statements',
            'accounting_policies': 'Accounting Policies',
            'md&a': "Management's Discussion and Analysis",
            'financial_statements': 'Financial Statements',
            'cover': 'Cover Pages',
            'other': 'Other Content'
        }
        return type_names.get(section_type, 'Other Content')
    
    def _detect_individual_notes(self):
        """Detect individual notes within Notes section."""
        notes_sections = [s for s in self.sections if s.section_type == 'notes']
        
        for section in notes_sections:
            # Find individual note boundaries
            note_matches = []
            for pattern in self.NOTE_PATTERNS:
                matches = re.finditer(pattern, section.text, re.MULTILINE | re.IGNORECASE)
                for m in matches:
                    note_matches.append({
                        'position': m.start(),
                        'number': m.group(1),
                        'title': m.group(2).strip() if len(m.groups()) > 1 else ''
                    })
            
            # Sort by position and store as metadata
            note_matches.sort(key=lambda x: x['position'])
            section.note_boundaries = note_matches
    
    def get_section_by_type(self, section_type: str) -> list[Section]:
        """Get all sections of a specific type."""
        return [s for s in self.sections if s.section_type == section_type]
    
    def get_notes_section(self) -> Optional[Section]:
        """Get the Notes to Financial Statements section."""
        notes = self.get_section_by_type('notes')
        return notes[0] if notes else None
    
    def get_text_for_pages(self, start_page: int, end_page: int) -> str:
        """Get combined text for a page range."""
        text_parts = []
        for page in self.pages:
            if start_page <= page['page_num'] <= end_page:
                text_parts.append(f"[PAGE {page['page_num']}]\n{page['text']}")
        return "\n\n".join(text_parts)


def parse_document(pdf_path: str) -> ParsedDocument:
    """Convenience function to parse a PDF."""
    parser = DocumentParser(pdf_path)
    return parser.parse()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python stage1_parser.py <pdf_path>")
        sys.exit(1)
    
    doc = parse_document(sys.argv[1])
    
    print(f"\n{'='*60}")
    print(f"PARSING COMPLETE: {doc.filename}")
    print(f"{'='*60}")
    print(f"Total pages: {doc.total_pages}")
    print(f"Sections found: {len(doc.sections)}")
    print(f"Tables found: {len(doc.tables)}")
    print(f"\nSections:")
    for s in doc.sections:
        print(f"  - {s.name} ({s.section_type}): pages {s.start_page}-{s.end_page}")
