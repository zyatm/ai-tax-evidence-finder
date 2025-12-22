"""
Stage 2: Verbatim Evidence Extractor
====================================
LLM-powered extraction of verbatim financial evidence from SEC 10-K filings.
Uses block-chunking (6 API calls) to control costs.

Blocks:
1. Fixed Assets (8 categories)
2. Inventory (1 category)
3. R&D (1 category)
4. Tax (6 categories)
5. Financial Statements (3 categories)
6. Business Overview (1 category)
"""

import os
import json
import re
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict
import anthropic

# Import from stage 1
try:
    from .stage1_parser import ParsedDocument, Section
except ImportError:
    from stage1_parser import ParsedDocument, Section


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Evidence:
    """Single piece of extracted evidence."""
    text: str
    page: int
    section: str
    match_keyword: str
    confidence: str  # HIGH, MEDIUM, LOW
    verified: bool = False
    
    def to_dict(self) -> Dict:
        return {
            'text': self.text,
            'page': self.page,
            'section': self.section,
            'match_keyword': self.match_keyword,
            'confidence': self.confidence,
            'verified': self.verified
        }


@dataclass 
class CategoryExtraction:
    """Extraction results for a single category."""
    block: str
    category: str
    evidence: List[Evidence] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            'block': self.block,
            'category': self.category,
            'evidence': [e.to_dict() for e in self.evidence]
        }


@dataclass
class ExtractionResult:
    """Complete extraction results."""
    document_id: str
    extractions: List[CategoryExtraction] = field(default_factory=list)
    audit: List[Dict] = field(default_factory=list)
    total_evidence: int = 0
    verified_count: int = 0
    cost_estimate: float = 0.0
    tokens_used: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'document_id': self.document_id,
            'extractions': [e.to_dict() for e in self.extractions],
            'audit': self.audit,
            'totals': {
                'evidence_count': self.total_evidence,
                'verified_count': self.verified_count,
                'cost_estimate': self.cost_estimate,
                'tokens_used': self.tokens_used
            }
        }


# =============================================================================
# PROMPTS
# =============================================================================

SYSTEM_PROMPT = """You are a TAX WORKPAPER EVIDENCE EXTRACTOR for SEC 10-K filings.

MISSION
Create an audit-ready evidence binder for tax method-change analysis by extracting ONLY verbatim quotes from the provided document text. This is not a summary task.

NON-NEGOTIABLE RULES
1) VERBATIM ONLY: Every quote must be copied exactly from the provided text. Never paraphrase. Never "clean up" wording.
2) PAGE REQUIRED: Every quote must include the page number from the nearest preceding [PAGE X] marker.
3) NO HALLUCINATIONS: If evidence is not present for a category, return an empty evidence array for that category.
4) JSON ONLY: Output must be valid JSON only. No prose, no markdown.
5) CONTIGUOUS TEXT ONLY: Do not stitch together text from multiple locations. Each quote must be a single continuous excerpt from one area of the document.
6) EVIDENCE QUALITY: Prefer accounting policy language and disclosure language (Notes / Significant Accounting Policies). Avoid headings-only unless nothing else exists.
7) LENGTH: Each evidence quote should typically be 1–5 sentences or one paragraph (enough to stand alone).
8) TRACEABILITY: Include the keyword/trigger you used and a short section label (best-effort).

SECTION LABELING (best-effort)
- If nearby text includes "Note", "Notes to Consolidated Financial Statements", "Significant Accounting Policies" → section="Notes"
- If includes "Item 7" or "Management's Discussion and Analysis" → section="MD&A"
- If includes "Balance Sheets", "Statements of Operations", "Statements of Cash Flows" → section="Financial Statements"
- Else section="Other"

CONFIDENCE
- HIGH: direct policy/disclosure text clearly about the category
- MEDIUM: relevant but indirect disclosure or mixed content
- LOW: weak match (keyword appears but context is unclear)

RETURN STRUCTURE
Return JSON exactly matching the schema provided in the user prompt."""


# Block definitions with categories and keywords
# Keywords expanded based on golden standard document analysis
BLOCKS = {
    "Fixed Assets": {
        "categories": {
            "Depreciation/Amortization": [
                "depreciation", "amortization", "useful life", "useful lives", "straight-line", 
                "accumulated depreciation", "depreciation expense", "amortization expense",
                "estimated useful life", "depreciable life", "rig utilization", 
                "depreciation and amortization expense"
            ],
            "Intangibles": [
                "intangible assets", "intangible asset", "goodwill", "patents", "trademarks", 
                "customer relationships", "indefinite-lived", "definite-lived", "impairment",
                "contract intangible", "drilling contract intangible"
            ],
            "Property, Plant & Equipment": [
                "property, plant and equipment", "property plant equipment", "property and equipment",
                "PP&E", "fixed assets", "machinery", "equipment", "construction in progress", 
                "leasehold improvements", "drilling units", "drilling rigs", "fleet"
            ],
            "Repair & Maintenance": [
                "repair", "repairs", "maintenance", "turnaround", "overhaul", "major maintenance",
                "maintenance and repair", "operating and maintenance", "component overhaul",
                "major overhaul", "third-party vendor", "maintenance cost", "maintenance costs",
                "PBH", "power-by-the-hour", "repairs and maintenance", "costs and expenses"
            ],
            "Spare Parts": [
                "spare parts", "critical spares", "rotables", "rotable parts", "catalysts", 
                "repairable spares", "consumable spare", "capital spare", "materials and supplies",
                "spare parts and equipment", "maintenance inventory"
            ],
            "Building/Leasehold": [
                "building", "buildings", "leasehold improvement", "tenant improvement",
                "land and buildings", "facilities", "buildings and improvement", 
                "buildings and improvements", "useful life of our"
            ],
            "M&A/Acquisition": [
                "acquisition", "acquisitions", "merger", "business combination", "purchase price allocation",
                "acquired", "we acquired", "fair value of", "noncash consideration", "transferred",
                "investment and acquisition", "perestroika"
            ],
            "Expansion & Construction": [
                "expansion", "construction", "capital project", "capex", "construction-in-progress",
                "capital expenditure", "capital expenditures", "new facility", "capacity expansion"
            ]
        },
        "priority_sections": ["notes", "accounting_policies", "md&a"]  # Added MD&A
    },
    "Inventory": {
        "categories": {
            "Inventory": [
                "inventory", "inventories", "LIFO", "FIFO", "weighted average", "lower of cost", 
                "net realizable value", "263A", "UNICAP", "raw materials", "work in process",
                "finished goods"
            ]
        },
        "priority_sections": ["notes", "accounting_policies", "md&a"]  # Added MD&A
    },
    "R&D": {
        "categories": {
            "Research & Development": [
                "research and development", "R&D", "development costs", "capitalized software",
                "joint venture", "joint ventures", "technological innovation", "equity investment",
                "equity investments", "unconsolidated affiliates", "innovation",
                "we procure and provide", "unconsolidated companies"
            ]
        },
        "priority_sections": ["notes", "md&a"]
    },
    "Tax": {
        "categories": {
            "Section 163(j)": [
                "163(j)", "business interest", "interest limitation", "interest expense limitation",
                "ATI", "adjusted taxable income", "interest expense, net", "capitalized interest",
                "interest expense was"
            ],
            "Deferred Tax (DTL/DTA)": [
                "deferred tax", "deferred tax assets", "deferred tax liabilities", "valuation allowance", 
                "temporary differences", "ASC 740", "income tax", "tax provision"
            ],
            "Prepaid Expense": [
                "prepaid", "prepaid expenses", "advance payment", "paid in advance",
                "contract fulfillment", "costs to fulfill", "fulfillment costs",
                "costs incurred in advance", "contract fulfillment costs"
            ],
            "Deferred Revenue": [
                "deferred revenue", "unearned revenue", "contract liability", "contract liabilities"
            ],
            "Advanced Payments": [
                "advance payment", "advanced payments", "customer advances", "deposits received", 
                "upfront payment", "customer deposits"
            ],
            "Revenue Recognition": [
                "revenue recognition", "ASC 606", "performance obligation", "contract asset", 
                "variable consideration", "revenues are recognized", "recognize revenue"
            ]
        },
        "priority_sections": ["notes", "accounting_policies", "md&a"]  # Added MD&A
    },
    "Financial Statements": {
        "categories": {
            "Income Statement": [
                "consolidated statements of operations", "statement of operations",
                "total revenue", "net income", "operating income", "gross profit"
            ],
            "Balance Sheet": [
                "consolidated balance sheets", "consolidated balance sheet",
                "total assets", "total liabilities", "stockholders' equity", "shareholders' equity"
            ],
            "Cash Flow": [
                "consolidated statements of cash flows", "statement of cash flows",
                "operating activities", "investing activities", "financing activities",
                "cash provided by", "cash used in"
            ]
        },
        "priority_sections": ["financial_statements", "notes"]
    },
    "Business Overview": {
        "categories": {
            "Business Description": [
                "we own and operate", "we are a leading", "leading provider", "we provide",
                "our business", "our operations", "we operate", "our company", "our services",
                "principal business", "business overview"
            ]
        },
        "priority_sections": ["md&a", "business", "notes"]  # Added business section
    }
}


def build_user_prompt(block_name: str, categories: Dict, document_id: str, document_text: str) -> str:
    """Build user prompt for a specific block."""
    
    # Build category list
    category_lines = []
    idx = 1
    for cat_name, keywords in categories.items():
        kw_str = ", ".join(keywords)
        category_lines.append(f"{idx}) {cat_name}\n   Keywords: {kw_str}")
        idx += 1
    
    categories_str = "\n".join(category_lines)
    
    return f"""Extract an audit-ready evidence binder from this 10-K excerpt.

CATEGORIES (extract 1–3 evidence quotes per category):
{categories_str}

INSTRUCTIONS
- Use keywords to locate relevant passages.
- Extract the surrounding paragraph or 2–6 sentences around the hit.
- Each quote MUST be copied exactly as-is from the document text.
- Each quote MUST include the page number from [PAGE X].
- If nothing found, evidence array must be [] for that category.

OUTPUT JSON SCHEMA (exactly):
{{
  "document_id": "{document_id}",
  "block": "{block_name}",
  "extractions": [
    {{
      "category": "<Category Name>",
      "evidence": [
        {{
          "text": "<verbatim quote>",
          "page": <integer>,
          "section": "<Notes | MD&A | Financial Statements | Other>",
          "match_keyword": "<keyword used>",
          "confidence": "HIGH | MEDIUM | LOW"
        }}
      ]
    }}
  ],
  "audit": [
    {{ "category": "<Category Name>", "keyword": "<keyword>", "page": <integer> }}
  ]
}}

DOCUMENT_ID: {document_id}

DOCUMENT TEXT (contains [PAGE X] markers):
{document_text}"""


# =============================================================================
# EXTRACTOR CLASS
# =============================================================================

class VerbatimExtractor:
    """
    Stage 2: Extract verbatim evidence using Claude API.
    Makes one API call per block (5 total) to control costs.
    """

    # Cost per million tokens (Claude Sonnet 4)
    INPUT_COST_PER_M = 3.00
    OUTPUT_COST_PER_M = 15.00
    MODEL = "claude-sonnet-4-20250514"

    def __init__(self, api_key: Optional[str] = None, config_path: Optional[str] = None):
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self.client = anthropic.Anthropic(api_key=self.api_key)

        # Token tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        # Load configuration
        self._load_config(config_path)

    def _load_config(self, config_path: Optional[str] = None):
        """Load configuration from JSON file or use defaults."""
        if config_path:
            config_file = Path(config_path)
            if not config_file.exists():
                raise FileNotFoundError(f"Config file not found: {config_path}")

            print(f"[Config] Loading custom configuration from: {config_path}")
            with open(config_file) as f:
                config = json.load(f)

            # Load prompts
            self.system_prompt = config.get('prompts', {}).get('system_prompt', SYSTEM_PROMPT)
            self.user_prompt_template = config.get('prompts', {}).get('user_prompt_template')

            # Load blocks
            self.blocks = config.get('blocks', BLOCKS)

            # Load model settings
            model_config = config.get('model', {})
            self.MODEL = model_config.get('name', self.MODEL)
            self.INPUT_COST_PER_M = model_config.get('input_cost_per_m', self.INPUT_COST_PER_M)
            self.OUTPUT_COST_PER_M = model_config.get('output_cost_per_m', self.OUTPUT_COST_PER_M)

            print(f"[Config] Using model: {self.MODEL}")
            print(f"[Config] Loaded {len(self.blocks)} blocks")
        else:
            # Use defaults
            self.system_prompt = SYSTEM_PROMPT
            self.user_prompt_template = None
            self.blocks = BLOCKS

    def extract(self, doc: ParsedDocument) -> ExtractionResult:
        """
        Extract verbatim evidence from parsed document.
        Makes one API call per block.
        """
        document_id = Path(doc.filename).stem
        print(f"\n[Stage 2] Extracting evidence from: {doc.filename}")
        print(f"[Stage 2] Document ID: {document_id}")
        
        all_extractions = []
        all_audit = []

        for block_name, block_config in self.blocks.items():
            print(f"\n  Processing block: {block_name} ({len(block_config['categories'])} categories)")
            
            # Get relevant text for this block
            section_text = self._get_priority_text(doc, block_config)
            
            if not section_text.strip():
                print(f"    ⚠ No relevant text found for {block_name}")
                # Add empty extractions for all categories in this block
                for cat_name in block_config['categories']:
                    all_extractions.append(CategoryExtraction(
                        block=block_name,
                        category=cat_name,
                        evidence=[]
                    ))
                continue
            
            # Make API call for this block
            block_result = self._extract_block(
                block_name=block_name,
                categories=block_config['categories'],
                document_id=document_id,
                section_text=section_text,
                full_text=doc.full_text  # For verification
            )
            
            all_extractions.extend(block_result['extractions'])
            all_audit.extend(block_result['audit'])
            
            # Rate limiting between blocks
            time.sleep(0.5)
        
        # Calculate totals
        total_evidence = sum(len(e.evidence) for e in all_extractions)
        verified_count = sum(
            sum(1 for ev in e.evidence if ev.verified)
            for e in all_extractions
        )
        cost = self._calculate_cost()
        
        result = ExtractionResult(
            document_id=document_id,
            extractions=all_extractions,
            audit=all_audit,
            total_evidence=total_evidence,
            verified_count=verified_count,
            cost_estimate=cost,
            tokens_used={
                'input': self.total_input_tokens,
                'output': self.total_output_tokens
            }
        )
        
        print(f"\n[Stage 2] Complete:")
        print(f"  Total evidence items: {total_evidence}")
        if total_evidence > 0:
            print(f"  Verified quotes: {verified_count}/{total_evidence} ({verified_count/total_evidence*100:.0f}%)")
        else:
            print("  No evidence found")
        print(f"  Estimated cost: ${cost:.4f}")
        
        return result
    
    def _get_priority_text(self, doc: ParsedDocument, block_config: Dict) -> str:
        """
        Get text from priority sections for a block.
        Uses keyword-guided chunking for large sections.
        """
        priority_sections = block_config.get('priority_sections', ['notes'])
        all_keywords = []
        for keywords in block_config['categories'].values():
            all_keywords.extend(keywords[:5])
        
        text_parts = []
        section_order = ['notes', 'accounting_policies', 'financial_statements', 'md&a', 'business']
        
        for section_type in section_order:
            if section_type in priority_sections:
                matching_sections = [
                    s for s in doc.sections if s.section_type == section_type
                ]
                for section in matching_sections:
                    if len(section.text) > 60000:
                        # Use keyword-guided chunking for large sections
                        chunks = self._extract_relevant_chunks(section.text, all_keywords)
                        text_parts.append(f"=== {section.name} (excerpts) ===\n{chunks}")
                    else:
                        text_parts.append(f"=== {section.name} ===\n{section.text[:50000]}")
        
        # Fallback to full text if no priority sections found
        if not text_parts:
            text_parts.append(doc.full_text[:80000])
        
        return "\n\n".join(text_parts)
    
    def _score_chunk(self, chunk_text: str) -> int:
        """
        Score a chunk by financial relevance.
        Higher scores indicate more likely to contain actual financial evidence.
        """
        score = 0
        text_lower = chunk_text.lower()
        
        # HIGH VALUE: Financial specifics (+30, +20, +10)
        if re.search(r'\$[\d,]+\s*(million|billion|thousand)?', text_lower):
            score += 30  # Has dollar amounts
        if re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s+\d{4}', text_lower):
            score += 20  # Specific date (Month DD, YYYY)
        elif re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}', text_lower):
            score += 15  # Month Year
        if re.search(r'(fiscal\s+)?(year|years)\s+(ended|ending)', text_lower):
            score += 10  # Fiscal year reference
        if re.search(r'december\s+31,?\s+\d{4}', text_lower):
            score += 10  # Balance sheet date
        
        # MEDIUM VALUE: Accounting policy language (+5 each)
        policy_terms = [
            'fair value', 'consideration', 'recognized', 'transferred', 
            'aggregate', 'purchase price', 'allocated', 'carrying amount',
            'useful life', 'depreciation', 'amortization', 'impairment',
            'deferred tax', 'valuation allowance', 'intangible asset',
            'straight-line', 'weighted average', 'cost basis'
        ]
        for term in policy_terms:
            if term in text_lower:
                score += 5
        
        # BONUS: Tables with numbers (+15)
        if re.search(r'\d+\s+\d+\s+\d+', chunk_text):  # Multiple numbers in sequence (table-like)
            score += 15
        
        # NEGATIVE: Generic forward-looking language (-10 each)
        generic_terms = [
            'may pursue', 'could result', 'risks and uncertainties',
            'forward-looking', 'no assurance', 'cannot predict',
            'subject to change', 'may not be indicative'
        ]
        for term in generic_terms:
            if term in text_lower:
                score -= 10
        
        # NEGATIVE: Boilerplate (-5)
        if 'table of contents' in text_lower:
            score -= 20
        
        return score
    
    def _extract_relevant_chunks(
        self, 
        text: str, 
        keywords: List[str], 
        chunk_size: int = 3000, 
        max_chunks: int = 15
    ) -> str:
        """
        Extract text chunks around keyword matches using relevance scoring.
        
        Instead of first-come-first-served, this:
        1. Finds ALL keyword matches
        2. Scores each chunk by financial relevance
        3. Deduplicates overlapping chunks
        4. Returns top N by score
        """
        text_lower = text.lower()
        scored_chunks = []
        seen_ranges = set()
        
        # Sort keywords by length descending (prefer longer, more specific matches)
        sorted_keywords = sorted(keywords, key=len, reverse=True)
        
        # Step 1: Find ALL keyword matches and score them
        for keyword in sorted_keywords:
            if len(keyword) < 3:
                continue
            
            # Use word boundaries for short keywords to avoid partial matches
            escaped = re.escape(keyword.lower())
            if len(keyword) <= 4:
                pattern = r'\b' + escaped + r'\b'
            else:
                pattern = escaped
            
            for match in re.finditer(pattern, text_lower):
                start = max(0, match.start() - chunk_size // 2)
                end = min(len(text), match.end() + chunk_size // 2)
                
                # Snap to paragraph boundaries
                while start > 0 and text[start] not in '\n':
                    start -= 1
                while end < len(text) and text[end] not in '\n':
                    end += 1
                
                # Check for overlap (dedupe)
                range_key = (start // 1000, end // 1000)
                if range_key not in seen_ranges:
                    seen_ranges.add(range_key)
                    
                    # Get page marker
                    page_match = re.search(r'\[PAGE\s+(\d+)\]', text[max(0, start-200):start])
                    page_marker = page_match.group(0) if page_match else ""
                    
                    chunk = text[start:end].strip()
                    if page_marker and page_marker not in chunk:
                        chunk = f"{page_marker}\n{chunk}"
                    
                    # Score this chunk
                    score = self._score_chunk(chunk)
                    
                    scored_chunks.append({
                        'chunk': chunk,
                        'score': score,
                        'keyword': keyword,
                        'position': start
                    })
        
        # Step 2: Sort by score (descending), then by position (ascending) as tiebreaker
        scored_chunks.sort(key=lambda x: (-x['score'], x['position']))
        
        # Step 3: Take top N chunks
        top_chunks = [c['chunk'] for c in scored_chunks[:max_chunks]]
        
        return "\n\n---\n\n".join(top_chunks)
    
    def _extract_block(
        self,
        block_name: str,
        categories: Dict,
        document_id: str,
        section_text: str,
        full_text: str
    ) -> Dict:
        """Make API call to extract evidence for one block."""

        # Use custom user prompt template if provided, otherwise use default builder
        if self.user_prompt_template:
            # Build category list for template
            category_lines = []
            idx = 1
            for cat_name, keywords in categories.items():
                kw_str = ", ".join(keywords)
                category_lines.append(f"{idx}) {cat_name}\n   Keywords: {kw_str}")
                idx += 1
            categories_str = "\n".join(category_lines)

            user_prompt = self.user_prompt_template.format(
                categories=categories_str,
                document_id=document_id,
                block_name=block_name,
                document_text=section_text[:45000]
            )
        else:
            user_prompt = build_user_prompt(
                block_name=block_name,
                categories=categories,
                document_id=document_id,
                document_text=section_text[:45000]  # Token limit safety
            )

        try:
            response = self.client.messages.create(
                model=self.MODEL,
                max_tokens=4000,
                system=self.system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            
            # Track tokens
            self.total_input_tokens += response.usage.input_tokens
            self.total_output_tokens += response.usage.output_tokens
            
            # Parse response
            response_text = response.content[0].text
            
            # Extract JSON
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                result_json = json.loads(json_match.group())
            else:
                print(f"    ⚠ Could not parse JSON for {block_name}")
                result_json = {"extractions": [], "audit": []}
                
        except json.JSONDecodeError as e:
            print(f"    ⚠ JSON parse error for {block_name}: {e}")
            result_json = {"extractions": [], "audit": []}
        except Exception as e:
            print(f"    ⚠ API error for {block_name}: {e}")
            result_json = {"extractions": [], "audit": []}
        
        # Build CategoryExtraction objects with verification
        extractions = []
        
        # Create a map of category name -> extraction data
        extraction_map = {
            e.get('category', ''): e 
            for e in result_json.get('extractions', [])
        }
        
        for cat_name in categories.keys():
            extraction_data = extraction_map.get(cat_name, {'evidence': []})
            
            evidence_list = []
            for ev in extraction_data.get('evidence', []):
                evidence_text = ev.get('text', '')
                
                # Verify quote exists in source
                verified = self._verify_evidence(evidence_text, full_text)
                
                evidence_list.append(Evidence(
                    text=evidence_text,
                    page=ev.get('page', 0),
                    section=ev.get('section', 'Other'),
                    match_keyword=ev.get('match_keyword', ''),
                    confidence=ev.get('confidence', 'MEDIUM'),
                    verified=verified
                ))
            
            extractions.append(CategoryExtraction(
                block=block_name,
                category=cat_name,
                evidence=evidence_list
            ))
            
            # Log results
            if evidence_list:
                verified_count = sum(1 for e in evidence_list if e.verified)
                print(f"    ✓ {cat_name}: {len(evidence_list)} evidence ({verified_count} verified)")
            else:
                print(f"    ○ {cat_name}: no evidence found")
        
        return {
            'extractions': extractions,
            'audit': result_json.get('audit', [])
        }
    
    def _verify_evidence(self, evidence_text: str, source_text: str) -> bool:
        """
        Verify that evidence text exists in source document.
        Uses fuzzy matching to handle minor OCR/extraction variations.
        """
        if not evidence_text or len(evidence_text) < 20:
            return False
        
        # Normalize whitespace
        evidence_clean = re.sub(r'\s+', ' ', evidence_text.lower().strip())
        source_clean = re.sub(r'\s+', ' ', source_text.lower())
        
        # Direct substring match (first 100 chars)
        if evidence_clean[:100] in source_clean:
            return True
        
        # Word-based fuzzy match (60% threshold)
        evidence_words = set(w for w in evidence_clean.split() if len(w) > 3)
        if not evidence_words:
            return False
        
        matches = sum(1 for word in evidence_words if word in source_clean)
        return matches >= len(evidence_words) * 0.6
    
    def _calculate_cost(self) -> float:
        """Calculate estimated API cost."""
        input_cost = (self.total_input_tokens / 1_000_000) * self.INPUT_COST_PER_M
        output_cost = (self.total_output_tokens / 1_000_000) * self.OUTPUT_COST_PER_M
        return input_cost + output_cost


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def extract_verbatim(doc: ParsedDocument, api_key: Optional[str] = None) -> ExtractionResult:
    """Convenience function for verbatim extraction."""
    extractor = VerbatimExtractor(api_key)
    return extractor.extract(doc)


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import sys
    from stage1_parser import parse_document
    
    if len(sys.argv) < 2:
        print("Usage: python stage2_verbatim.py <pdf_path>")
        sys.exit(1)
    
    # Parse document
    doc = parse_document(sys.argv[1])
    
    # Extract evidence
    result = extract_verbatim(doc)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"EXTRACTION COMPLETE: {result.document_id}")
    print(f"{'='*60}")
    
    print(f"\nBy block:")
    for block_name in BLOCKS.keys():
        block_extractions = [e for e in result.extractions if e.block == block_name]
        block_evidence = sum(len(e.evidence) for e in block_extractions)
        block_verified = sum(sum(1 for ev in e.evidence if ev.verified) for e in block_extractions)
        if block_evidence > 0:
            print(f"  {block_name}: {block_evidence} evidence ({block_verified} verified)")
    
    print(f"\nTotals:")
    print(f"  Evidence items: {result.total_evidence}")
    print(f"  Verified: {result.verified_count}")
    print(f"  Cost: ${result.cost_estimate:.4f}")
    
    # Output JSON
    output_file = Path(sys.argv[1]).stem + "_extraction.json"
    with open(output_file, 'w') as f:
        json.dump({
            'document_id': result.document_id,
            'extractions': [
                {
                    'block': e.block,
                    'category': e.category,
                    'evidence': [
                        {
                            'text': ev.text,
                            'page': ev.page,
                            'section': ev.section,
                            'match_keyword': ev.match_keyword,
                            'confidence': ev.confidence,
                            'verified': ev.verified
                        }
                        for ev in e.evidence
                    ]
                }
                for e in result.extractions
            ],
            'audit': result.audit,
            'totals': {
                'evidence_count': result.total_evidence,
                'verified_count': result.verified_count,
                'cost_estimate': result.cost_estimate
            }
        }, f, indent=2)
    
    print(f"\nJSON output: {output_file}")
