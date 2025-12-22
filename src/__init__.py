"""
AI Tax Intelligence - 10-K Evidence Extraction Engine

Modules:
    stage1_parser: PDF parsing and section detection
    stage2_verbatim: LLM-powered evidence extraction
    stage3_summary: Evidence summarization (optional)
    stage4_excel: Excel output generation
"""

from .stage1_parser import parse_document, ParsedDocument, Section
from .stage2_verbatim import VerbatimExtractor, ExtractionResult, Evidence, CategoryExtraction

__version__ = "1.0.0"
__all__ = [
    'parse_document',
    'ParsedDocument', 
    'Section',
    'VerbatimExtractor',
    'ExtractionResult',
    'Evidence',
    'CategoryExtraction'
]
