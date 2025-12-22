# Configuration Guide

This directory contains configuration files that allow you to customize the AI Tax Evidence Finder without modifying Python code.

## Quick Start

### Using Default Configuration
```bash
# No config needed - uses built-in defaults
python run.py extract company_10K.pdf
```

### Using Custom Configuration
```bash
# Use your custom config
python run.py extract company_10K.pdf --config config/custom_example.json
```

---

## Configuration File Structure

A configuration file is a JSON file with three main sections:

```json
{
  "prompts": { ... },    // System and user prompts for Claude
  "blocks": { ... },     // Categories and keywords to extract
  "model": { ... }       // Model settings and pricing
}
```

---

## Section 1: Prompts

### System Prompt
The system prompt defines Claude's role and extraction rules.

**When to customize:**
- Change evidence length (e.g., "2-8 sentences" instead of "1-5 sentences")
- Adjust confidence criteria
- Add industry-specific guidance
- Modify section labeling rules

**Example:**
```json
{
  "prompts": {
    "system_prompt": "You are a TAX WORKPAPER EVIDENCE EXTRACTOR...\n\n7) LENGTH: Each evidence quote should typically be 2-8 sentences..."
  }
}
```

### User Prompt Template
The user prompt is sent with each API call. Uses Python string formatting.

**Available variables:**
- `{categories}` - List of categories and keywords
- `{document_id}` - Document identifier
- `{block_name}` - Current block being processed
- `{document_text}` - The document text to analyze

**When to customize:**
- Change extraction instructions
- Modify output format requirements
- Add specific business context

---

## Section 2: Blocks and Categories

This is where you define **what** to extract.

### Block Structure
```json
{
  "blocks": {
    "Block Name": {
      "categories": {
        "Category Name": ["keyword1", "keyword2", "keyword3"]
      },
      "priority_sections": ["notes", "md&a"]
    }
  }
}
```

### Adding New Categories

**Example: Add cryptocurrency tracking for tech companies**
```json
{
  "blocks": {
    "Fixed Assets": {
      "categories": {
        "Digital Assets": [
          "cryptocurrency",
          "digital assets",
          "bitcoin",
          "ethereum",
          "blockchain",
          "crypto holdings"
        ]
      }
    }
  }
}
```

### Adding Industry-Specific Keywords

**Example: Add oil & gas keywords**
```json
{
  "blocks": {
    "Fixed Assets": {
      "categories": {
        "Depreciation/Amortization": [
          "depreciation",
          "depletion",
          "DD&A",
          "proved reserves",
          "unit-of-production"
        ]
      }
    }
  }
}
```

### Priority Sections
Tells the extractor which document sections to focus on for each block.

**Options:**
- `"notes"` - Notes to Financial Statements
- `"accounting_policies"` - Significant Accounting Policies
- `"md&a"` - Management's Discussion & Analysis
- `"financial_statements"` - Income Statement, Balance Sheet, Cash Flow
- `"business"` - Business Description

**Example:**
```json
{
  "blocks": {
    "Tax": {
      "priority_sections": ["notes", "accounting_policies", "md&a"]
    }
  }
}
```

---

## Section 3: Model Configuration

### Model Selection
```json
{
  "model": {
    "name": "claude-sonnet-4-20250514",
    "input_cost_per_m": 3.00,
    "output_cost_per_m": 15.00
  }
}
```

**Available models:**
- `claude-sonnet-4-20250514` - Fast, accurate, $0.25-0.35/doc (recommended)
- `claude-opus-4-5-20251101` - Most accurate, $1.50-2.00/doc

**When to use Opus:**
- Complex documents requiring highest accuracy
- Critical tax matters where errors are costly
- Documents with unusual formatting

---

## Common Customization Scenarios

### Scenario 1: Technology Company Focus

Create `config/tech_focus.json`:
```json
{
  "blocks": {
    "Fixed Assets": {
      "categories": {
        "Software Development": [
          "capitalized software",
          "internal-use software",
          "software development costs",
          "agile development"
        ],
        "Cloud Infrastructure": [
          "cloud computing",
          "SaaS",
          "infrastructure as a service",
          "platform costs"
        ]
      }
    },
    "Tax": {
      "categories": {
        "Stock-Based Compensation": [
          "RSU",
          "restricted stock units",
          "stock options",
          "equity compensation"
        ]
      }
    }
  }
}
```

Usage:
```bash
python run.py extract tech_company_10K.pdf --config config/tech_focus.json
```

---

### Scenario 2: Manufacturing Company Focus

Create `config/manufacturing_focus.json`:
```json
{
  "blocks": {
    "Fixed Assets": {
      "categories": {
        "Manufacturing Equipment": [
          "manufacturing equipment",
          "production machinery",
          "assembly lines",
          "tooling",
          "molds and dies"
        ],
        "Facility Improvements": [
          "plant improvements",
          "factory expansion",
          "production facility"
        ]
      }
    },
    "Inventory": {
      "categories": {
        "Inventory": [
          "inventory",
          "LIFO",
          "FIFO",
          "work in process",
          "raw materials",
          "finished goods",
          "UNICAP",
          "263A"
        ]
      }
    }
  }
}
```

---

### Scenario 3: More Detailed Evidence

Create `config/detailed_extraction.json`:
```json
{
  "prompts": {
    "system_prompt": "You are a TAX WORKPAPER EVIDENCE EXTRACTOR for SEC 10-K filings.\n\n...\n\n7) LENGTH: Each evidence quote should typically be 3-10 sentences or 1-2 full paragraphs to provide maximum context.\n\n...",

    "user_prompt_template": "Extract an audit-ready evidence binder from this 10-K excerpt.\n\nCATEGORIES (extract 2-5 evidence quotes per category for comprehensive coverage):\n{categories}\n\nINSTRUCTIONS\n- Use keywords to locate relevant passages.\n- Extract full paragraphs or 3-10 sentences around the hit for complete context.\n- Each quote MUST be copied exactly as-is from the document text.\n- Each quote MUST include the page number from [PAGE X].\n- If nothing found, evidence array must be [] for that category.\n\n..."
  }
}
```

---

### Scenario 4: Cost Optimization (Shorter Extracts)

Create `config/cost_optimized.json`:
```json
{
  "prompts": {
    "system_prompt": "You are a TAX WORKPAPER EVIDENCE EXTRACTOR for SEC 10-K filings.\n\n...\n\n7) LENGTH: Each evidence quote should be 1-3 sentences maximum (concise extracts only).\n\n..."
  },

  "model": {
    "name": "claude-sonnet-4-20250514",
    "input_cost_per_m": 3.00,
    "output_cost_per_m": 15.00
  }
}
```

---

## Testing Your Configuration

### Step 1: Create Your Config
Copy `default_config.json` and modify:
```bash
cp config/default_config.json config/my_config.json
# Edit config/my_config.json with your changes
```

### Step 2: Test on Sample Document
```bash
python run.py extract test_10K.pdf --config config/my_config.json
```

### Step 3: Review Results
Check the output Excel file and verify:
- Are the right categories being extracted?
- Do keywords capture relevant evidence?
- Is evidence length appropriate?
- Is confidence scoring accurate?

### Step 4: Iterate
Adjust keywords, prompts, or settings based on results and re-test.

---

## Configuration Tips

### Keyword Best Practices

✅ **DO:**
- Use specific phrases: `"section 163(j)"` not just `"interest"`
- Include variations: `"PP&E"`, `"property, plant and equipment"`
- Add industry jargon: `"rig utilization"` for oil & gas
- Keep 5-15 keywords per category

❌ **DON'T:**
- Use single letters: `"R"` will match too much
- Use overly generic terms: `"cost"` matches everything
- Duplicate keywords across categories
- Add more than 20 keywords per category (diminishing returns)

### Prompt Best Practices

✅ **DO:**
- Keep "VERBATIM ONLY" rule - prevents hallucinations
- Maintain page number requirement - critical for audit trail
- Test prompt changes on known documents first

❌ **DON'T:**
- Remove JSON-only requirement - breaks parsing
- Change output schema structure - will break Excel generation
- Make prompts too long (>2000 words)

---

## Troubleshooting

### Problem: No Evidence Found
**Solution:** Check if keywords match actual document language
```bash
# Test: Search PDF for your keywords manually first
pdftotext document.pdf - | grep -i "your keyword"
```

### Problem: Wrong Evidence Extracted
**Solution:** Make keywords more specific
```json
// Instead of:
"keywords": ["interest"]

// Use:
"keywords": ["interest expense", "163(j)", "interest limitation"]
```

### Problem: Too Much/Little Evidence
**Solution:** Adjust prompt length guidance and max chunks
```json
{
  "prompts": {
    "system_prompt": "...\n7) LENGTH: Each evidence quote should be 1-2 sentences only.\n..."
  }
}
```

### Problem: High Costs
**Solutions:**
1. Use Sonnet instead of Opus
2. Reduce evidence length in prompts
3. Limit categories to only what you need
4. Remove unused blocks entirely

---

## Version Control

Track config changes in git:
```bash
git add config/my_config.json
git commit -m "Add custom config for oil & gas companies"
```

This allows you to:
- Revert to previous configs if needed
- See what changed between extractions
- Share configs with team members

---

## Integration with n8n

To use custom configs in n8n workflows:

```javascript
// n8n Execute Command Node
{
  "command": "python3 /app/run.py extract {{ $json.filepath }} --config /app/config/{{ $json.industry }}_config.json"
}
```

This allows users to select industry-specific configs via dropdown in n8n.

---

## Need Help?

1. Start with `default_config.json` - it's well-tested
2. Make small changes incrementally
3. Test on known documents
4. Check the logs for `[Config]` messages to verify your config loaded
5. Review examples in `custom_example.json`

---

## Files in This Directory

- `default_config.json` - Complete default configuration (reference)
- `custom_example.json` - Example showing tech/crypto customizations
- `README.md` - This file

Create your own configs as needed!
