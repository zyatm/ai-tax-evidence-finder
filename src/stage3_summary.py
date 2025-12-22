"""
Stage 3: Summary Generator
==========================
LLM-powered summary generation from verbatim extractions.
Generates tax-relevant summaries clearly marked as AI-generated.
"""

import os
import json
import re
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import anthropic

try:
    from .stage2_verbatim import ExtractionResult, CategoryExtraction
except ImportError:
    from stage2_verbatim import ExtractionResult, CategoryExtraction


@dataclass
class CategorySummary:
    """Summary for a single category."""
    category_id: str
    category_name: str
    summary: str  # Always prefixed with [AI SUMMARY]
    tax_opportunities: list[str] = field(default_factory=list)
    materiality: str = "UNKNOWN"  # HIGH, MEDIUM, LOW, UNKNOWN
    review_flags: list[str] = field(default_factory=list)


@dataclass
class SummaryResult:
    """Complete summary results."""
    filename: str
    summaries: dict[str, CategorySummary]
    cost_estimate: float
    tokens_used: dict


class SummaryGenerator:
    """
    Stage 3: Generate tax-relevant summaries from extractions.
    """
    
    # Cost per million tokens (Claude 3.5 Sonnet)
    INPUT_COST_PER_M = 3.00
    OUTPUT_COST_PER_M = 15.00
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.summary_prompt = self._load_summary_prompt()
        
        # Token tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0
    
    def _load_summary_prompt(self) -> str:
        """Load summary generation prompt."""
        prompt_path = Path(__file__).parent.parent / 'config' / 'summary_prompt.txt'
        with open(prompt_path) as f:
            return f.read()
    
    def generate(self, extraction_result: ExtractionResult) -> SummaryResult:
        """
        Generate summaries from extraction results.
        """
        print(f"\n[Stage 3] Generating summaries for: {extraction_result.filename}")
        
        summaries = {}
        
        # Group categories by block for efficient processing
        blocks = {}
        for cat_id, cat in extraction_result.categories.items():
            if cat.evidence:  # Only summarize categories with evidence
                block = cat.block
                if block not in blocks:
                    blocks[block] = {}
                blocks[block][cat_id] = cat
        
        # Process each block
        for block_name, block_categories in blocks.items():
            print(f"  Summarizing block: {block_name}")
            
            block_summaries = self._summarize_block(block_name, block_categories)
            summaries.update(block_summaries)
            
            time.sleep(0.3)  # Rate limiting
        
        # Add empty summaries for categories without evidence
        for cat_id, cat in extraction_result.categories.items():
            if cat_id not in summaries:
                summaries[cat_id] = CategorySummary(
                    category_id=cat_id,
                    category_name=cat.category_name,
                    summary="[AI SUMMARY] No evidence found in 10-K filing.",
                    materiality="UNKNOWN"
                )
        
        cost = self._calculate_cost()
        
        result = SummaryResult(
            filename=extraction_result.filename,
            summaries=summaries,
            cost_estimate=cost,
            tokens_used={
                'input': self.total_input_tokens,
                'output': self.total_output_tokens
            }
        )
        
        print(f"\n[Stage 3] Complete: {len([s for s in summaries.values() if 'No evidence' not in s.summary])} summaries generated, ${cost:.4f} estimated cost")
        
        return result
    
    def _summarize_block(
        self, 
        block_name: str, 
        categories: dict[str, CategoryExtraction]
    ) -> dict[str, CategorySummary]:
        """Summarize all categories in a block."""
        
        # Build evidence input for prompt
        evidence_input = []
        for cat_id, cat in categories.items():
            evidence_texts = []
            for e in cat.evidence:
                flag_str = f" [{', '.join(e.flags)}]" if e.flags else ""
                evidence_texts.append(f"  - [Page {e.page}]{flag_str}: {e.text[:500]}...")
            
            evidence_input.append(f"""
### {cat.category_name}
{chr(10).join(evidence_texts)}
""")
        
        evidence_str = "\n".join(evidence_input)
        
        prompt = f"""Analyze the following verbatim extractions from a 10-K filing and generate tax-relevant summaries.

BLOCK: {block_name}

EXTRACTED EVIDENCE:
{evidence_str}

For each category, provide:
1. A concise summary (2-4 sentences) prefixed with [AI SUMMARY]
2. Potential tax method change opportunities
3. Materiality assessment (HIGH/MEDIUM/LOW/UNKNOWN)
4. Any flags for items requiring further review

Respond with valid JSON:
{{
  "summaries": [
    {{
      "category": "Category Name",
      "summary": "[AI SUMMARY] Your summary here...",
      "tax_opportunities": ["opportunity 1", "opportunity 2"],
      "materiality": "HIGH|MEDIUM|LOW|UNKNOWN",
      "review_flags": ["flag if needed"]
    }}
  ]
}}"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                system=self.summary_prompt
            )
            
            self.total_input_tokens += response.usage.input_tokens
            self.total_output_tokens += response.usage.output_tokens
            
            response_text = response.content[0].text
            
            # Parse JSON
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                result_json = json.loads(json_match.group())
            else:
                result_json = {"summaries": []}
                
        except Exception as e:
            print(f"    Error summarizing {block_name}: {e}")
            result_json = {"summaries": []}
        
        # Build CategorySummary objects
        results = {}
        summary_map = {s['category']: s for s in result_json.get('summaries', [])}
        
        for cat_id, cat in categories.items():
            summary_data = summary_map.get(cat.category_name, {})
            
            summary_text = summary_data.get('summary', '')
            if not summary_text.startswith('[AI SUMMARY]'):
                summary_text = f"[AI SUMMARY] {summary_text}"
            
            results[cat_id] = CategorySummary(
                category_id=cat_id,
                category_name=cat.category_name,
                summary=summary_text,
                tax_opportunities=summary_data.get('tax_opportunities', []),
                materiality=summary_data.get('materiality', 'UNKNOWN'),
                review_flags=summary_data.get('review_flags', [])
            )
        
        return results
    
    def _calculate_cost(self) -> float:
        """Calculate estimated API cost."""
        input_cost = (self.total_input_tokens / 1_000_000) * self.INPUT_COST_PER_M
        output_cost = (self.total_output_tokens / 1_000_000) * self.OUTPUT_COST_PER_M
        return input_cost + output_cost


def generate_summaries(
    extraction_result: ExtractionResult, 
    api_key: Optional[str] = None
) -> SummaryResult:
    """Convenience function for summary generation."""
    generator = SummaryGenerator(api_key)
    return generator.generate(extraction_result)


if __name__ == "__main__":
    print("Stage 3 requires Stage 2 output. Run pipeline.py instead.")
