"""
Stage 2: Gemini Verbatim Evidence Extractor
============================================
Optimized for Google Gemini 2.0 Flash's high faithfulness (99.3%).
Uses structured output and direct prompting for best extraction quality.
"""

import os
import json
import re
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import google.generativeai as genai

# Import from stage 1
try:
    from .stage1_parser import ParsedDocument, Section
except ImportError:
    from stage1_parser import ParsedDocument, Section


@dataclass
class Evidence:
    """Single piece of extracted evidence."""
    text: str
    page: int
    section: str
    confidence: str  # HIGH, MEDIUM, LOW
    flags: list[str] = field(default_factory=list)
    verified: bool = False


@dataclass
class CategoryExtraction:
    """Extraction results for a single category."""
    category_id: str
    category_name: str
    block: str
    evidence: list[Evidence] = field(default_factory=list)
    raw_response: str = ""


@dataclass
class ExtractionResult:
    """Complete extraction results."""
    filename: str
    categories: dict[str, CategoryExtraction]
    total_evidence: int
    cost_estimate: float
    tokens_used: dict


class GeminiVerbatimExtractor:
    """
    Stage 2: Extract verbatim evidence using Google Gemini 2.0 Flash.
    
    Optimized for Gemini's strengths:
    - 99.3% factual consistency (best in class)
    - Excellent structured output
    - Cost effective ($0.075/$0.30 per MTok)
    - Fast inference
    """
    
    # Gemini 2.0 Flash pricing (per million tokens)
    INPUT_COST_PER_M = 0.075
    OUTPUT_COST_PER_M = 0.30
    
    MODEL = "gemini-2.0-flash-exp"  # Or "gemini-2.0-flash-001" for stable
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('GOOGLE_API_KEY')
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not set")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(
            self.MODEL,
            generation_config=genai.GenerationConfig(
                temperature=0,  # Deterministic for extraction
                top_p=1,
                max_output_tokens=4096,
            )
        )
        
        self.config = self._load_config()
        
        # Token tracking (estimated from character count)
        self.total_input_chars = 0
        self.total_output_chars = 0
        
    def _load_config(self) -> dict:
        """Load categories configuration."""
        config_path = Path(__file__).parent.parent / 'config' / 'categories.json'
        with open(config_path) as f:
            return json.load(f)
    
    def extract(self, doc: ParsedDocument) -> ExtractionResult:
        """Extract verbatim evidence from parsed document."""
        print(f"\n[Stage 2 - Gemini] Extracting evidence from: {doc.filename}")
        
        categories = {}
        blocks = self._group_categories_by_block()
        
        for block_name, block_categories in blocks.items():
            print(f"\n  Processing block: {block_name}")
            
            section_text = self._get_priority_text(doc, block_categories)
            
            if not section_text.strip():
                print(f"    No relevant text found for {block_name}")
                continue
            
            block_results = self._extract_block(
                block_name, 
                block_categories, 
                section_text,
                doc.filename
            )
            
            categories.update(block_results)
            time.sleep(0.3)  # Light rate limiting
        
        total_evidence = sum(len(c.evidence) for c in categories.values())
        cost = self._calculate_cost()
        
        result = ExtractionResult(
            filename=doc.filename,
            categories=categories,
            total_evidence=total_evidence,
            cost_estimate=cost,
            tokens_used={
                'input_chars': self.total_input_chars,
                'output_chars': self.total_output_chars,
                'estimated_input_tokens': self.total_input_chars // 4,
                'estimated_output_tokens': self.total_output_chars // 4
            }
        )
        
        print(f"\n[Stage 2 - Gemini] Complete: {total_evidence} evidence items, ${cost:.4f} estimated cost")
        
        return result
    
    def _group_categories_by_block(self) -> dict:
        """Group categories by their block for batch processing."""
        blocks = {}
        for cat_id, cat_config in self.config['categories'].items():
            block = cat_config['block']
            if block not in blocks:
                blocks[block] = {}
            blocks[block][cat_id] = cat_config
        return blocks
    
    def _get_priority_text(self, doc: ParsedDocument, categories: dict) -> str:
        """Get text from priority sections with keyword-guided chunking."""
        priority_sections = set()
        all_keywords = []
        for cat_config in categories.values():
            priority_sections.update(cat_config.get('priority_sections', []))
            all_keywords.extend(cat_config.get('keywords', [])[:5])
        
        text_parts = []
        section_order = ['notes', 'accounting_policies', 'md&a', 'financial_statements']
        
        for section_type in section_order:
            if section_type in priority_sections:
                matching_sections = [
                    s for s in doc.sections if s.section_type == section_type
                ]
                for section in matching_sections:
                    if len(section.text) > 60000:
                        chunks = self._extract_relevant_chunks(section.text, all_keywords)
                        text_parts.append(f"=== {section.name} (excerpts) ===\n{chunks}")
                    else:
                        text_parts.append(f"=== {section.name} ===\n{section.text[:50000]}")
        
        if not text_parts:
            text_parts.append(doc.full_text[:80000])
        
        return "\n\n".join(text_parts)
    
    def _extract_relevant_chunks(self, text: str, keywords: list, chunk_size: int = 3000, max_chunks: int = 15) -> str:
        """Extract text chunks around keyword matches."""
        text_lower = text.lower()
        chunks = []
        seen_ranges = set()
        
        for keyword in keywords:
            if len(keyword) < 3:
                continue
            pattern = re.escape(keyword.lower())
            
            for match in re.finditer(pattern, text_lower):
                start = max(0, match.start() - chunk_size // 2)
                end = min(len(text), match.end() + chunk_size // 2)
                
                # Snap to paragraph boundaries
                while start > 0 and text[start] not in '\n':
                    start -= 1
                while end < len(text) and text[end] not in '\n':
                    end += 1
                
                range_key = (start // 1000, end // 1000)
                if range_key not in seen_ranges:
                    seen_ranges.add(range_key)
                    
                    page_match = re.search(r'\[PAGE\s+(\d+)\]', text[max(0, start-200):start])
                    page_marker = page_match.group(0) if page_match else ""
                    
                    chunk = text[start:end].strip()
                    if page_marker and page_marker not in chunk:
                        chunk = f"{page_marker}\n{chunk}"
                    
                    chunks.append(chunk)
                    
                    if len(chunks) >= max_chunks:
                        break
            
            if len(chunks) >= max_chunks:
                break
        
        return "\n\n---\n\n".join(chunks[:max_chunks])
    
    def _extract_block(
        self, 
        block_name: str, 
        categories: dict, 
        section_text: str,
        filename: str
    ) -> dict[str, CategoryExtraction]:
        """Extract evidence for all categories in a block using Gemini."""
        
        # Build concise category list
        category_specs = []
        for cat_id, cat_config in categories.items():
            kw = ", ".join(cat_config['keywords'][:6])
            category_specs.append(f"• {cat_config['name']}: {kw}")
        
        categories_str = "\n".join(category_specs)
        
        # Gemini-optimized prompt: Direct, structured, with example
        prompt = f"""Extract VERBATIM quotes from this SEC 10-K for these categories:

{categories_str}

DOCUMENT:
{section_text[:45000]}

INSTRUCTIONS:
- Copy EXACT text from document (never paraphrase)
- Include [Page X] numbers when visible
- 1-3 quotes per category max
- Empty array if nothing found

Return ONLY this JSON structure:
{{
  "extractions": [
    {{
      "category": "Category Name",
      "evidence": [
        {{
          "text": "Exact quote from document",
          "page": 42,
          "section": "Note 5",
          "confidence": "HIGH"
        }}
      ]
    }}
  ]
}}"""

        self.total_input_chars += len(prompt)
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text
            self.total_output_chars += len(response_text)
            
            # Parse JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                result_json = json.loads(json_match.group())
            else:
                print(f"    Warning: Could not parse JSON for {block_name}")
                result_json = {"extractions": []}
                
        except Exception as e:
            print(f"    Error extracting {block_name}: {e}")
            result_json = {"extractions": []}
        
        # Build CategoryExtraction objects
        results = {}
        extraction_map = {e['category']: e for e in result_json.get('extractions', [])}
        
        for cat_id, cat_config in categories.items():
            cat_name = cat_config['name']
            extraction = extraction_map.get(cat_name, {'evidence': []})
            
            evidence_list = []
            for e in extraction.get('evidence', []):
                evidence_text = e.get('text', '')
                verified = self._verify_evidence(evidence_text, section_text)
                
                evidence_list.append(Evidence(
                    text=evidence_text,
                    page=e.get('page', 0),
                    section=e.get('section', ''),
                    confidence=e.get('confidence', 'MEDIUM'),
                    flags=['UNVERIFIED'] if not verified else [],
                    verified=verified
                ))
            
            results[cat_id] = CategoryExtraction(
                category_id=cat_id,
                category_name=cat_name,
                block=block_name,
                evidence=evidence_list,
                raw_response=response_text if evidence_list else ""
            )
            
            verified_count = sum(1 for e in evidence_list if e.verified)
            if evidence_list:
                print(f"    {cat_name}: {len(evidence_list)} evidence ({verified_count} verified)")
        
        return results
    
    def _verify_evidence(self, evidence_text: str, source_text: str) -> bool:
        """Verify that evidence text exists in source."""
        if not evidence_text or len(evidence_text) < 20:
            return False
        
        evidence_clean = re.sub(r'\s+', ' ', evidence_text.lower().strip())
        source_clean = re.sub(r'\s+', ' ', source_text.lower())
        
        # Direct match
        if evidence_clean[:100] in source_clean:
            return True
        
        # Word-based match
        evidence_words = set(evidence_clean.split())
        matches = sum(1 for word in evidence_words if word in source_clean and len(word) > 4)
        
        return matches >= len(evidence_words) * 0.6
    
    def _calculate_cost(self) -> float:
        """Calculate estimated API cost."""
        # Gemini uses characters, estimate 4 chars per token
        est_input_tokens = self.total_input_chars / 4
        est_output_tokens = self.total_output_chars / 4
        
        input_cost = (est_input_tokens / 1_000_000) * self.INPUT_COST_PER_M
        output_cost = (est_output_tokens / 1_000_000) * self.OUTPUT_COST_PER_M
        return input_cost + output_cost


# ============================================================================
# OPTIMIZED EXTRACTION PROMPTS BY CATEGORY
# ============================================================================

GEMINI_EXTRACTION_PROMPTS = {
    "Fixed Assets": """Extract verbatim evidence about FIXED ASSETS from this 10-K:

Categories:
• Depreciation/Amortization: useful life, depreciation methods, accumulated depreciation
• Intangibles: goodwill, patents, trademarks, software, indefinite-lived assets
• PP&E: property plant equipment, capitalization policies, asset schedules
• Repair/Maintenance: turnaround costs, major maintenance, sustaining capital
• Spare Parts: rotable parts, critical spares, catalysts
• Building/Leasehold: facility costs, tenant improvements, construction
• M&A: business combinations, purchase price allocation, acquired assets
• Expansion: capital projects, construction in progress, capacity expansion

DOCUMENT:
{text}

Return JSON with exact quotes only:
{{"extractions": [{{"category": "...", "evidence": [{{"text": "exact quote", "page": X, "section": "Note X", "confidence": "HIGH"}}]}}]}}""",

    "Inventory": """Extract verbatim evidence about INVENTORY from this 10-K:

Categories:
• Inventory: LIFO, FIFO, weighted average, raw materials, WIP, finished goods, 263A/UNICAP

DOCUMENT:
{text}

Return JSON with exact quotes only:
{{"extractions": [{{"category": "Inventory", "evidence": [{{"text": "exact quote", "page": X, "section": "Note X", "confidence": "HIGH"}}]}}]}}""",

    "R&D": """Extract verbatim evidence about RESEARCH & DEVELOPMENT from this 10-K:

Categories:
• Research and Development: R&D costs, Section 174, capitalized development, research credits

DOCUMENT:
{text}

Return JSON with exact quotes only:
{{"extractions": [{{"category": "Research and Development", "evidence": [{{"text": "exact quote", "page": X, "section": "Note X", "confidence": "HIGH"}}]}}]}}""",

    "Tax": """Extract verbatim evidence about TAX items from this 10-K:

Categories:
• Section 163(j): interest limitation, ATI, 30 percent, disallowed interest
• Deferred Tax: DTL, DTA, valuation allowance, temporary differences, NOL
• Prepaid Expense: prepaid insurance, prepaid rent, advance payments
• Deferred Revenue: unearned revenue, contract liabilities, customer deposits
• Advanced Payments: customer advances, prepayments received
• Revenue Recognition: ASC 606, performance obligations, contract revenue

DOCUMENT:
{text}

Return JSON with exact quotes only:
{{"extractions": [{{"category": "...", "evidence": [{{"text": "exact quote", "page": X, "section": "Note X", "confidence": "HIGH"}}]}}]}}""",

    "Financial Statements": """Extract verbatim evidence about FINANCIAL STATEMENTS from this 10-K:

Categories:
• Income Statement: revenue, cost of sales, operating income, net income totals
• Balance Sheet: total assets, total liabilities, stockholders equity
• Cash Flow: operating activities, investing activities, financing activities

DOCUMENT:
{text}

Return JSON with exact quotes only:
{{"extractions": [{{"category": "...", "evidence": [{{"text": "exact quote", "page": X, "section": "Statement/Note", "confidence": "HIGH"}}]}}]}}"""
}


def extract_with_gemini(doc: ParsedDocument, api_key: Optional[str] = None) -> ExtractionResult:
    """Convenience function for Gemini extraction."""
    extractor = GeminiVerbatimExtractor(api_key)
    return extractor.extract(doc)


if __name__ == "__main__":
    import sys
    from stage1_parser import parse_document
    
    if len(sys.argv) < 2:
        print("Usage: python stage2_gemini.py <pdf_path>")
        sys.exit(1)
    
    doc = parse_document(sys.argv[1])
    result = extract_with_gemini(doc)
    
    print(f"\n{'='*60}")
    print(f"GEMINI EXTRACTION COMPLETE: {result.filename}")
    print(f"{'='*60}")
    print(f"Total evidence items: {result.total_evidence}")
    print(f"Estimated cost: ${result.cost_estimate:.4f}")
    print(f"Characters processed: {result.tokens_used}")
    
    print(f"\nBy category:")
    for cat_id, cat in result.categories.items():
        if cat.evidence:
            verified = sum(1 for e in cat.evidence if e.verified)
            print(f"  {cat.category_name}: {len(cat.evidence)} items ({verified} verified)")
