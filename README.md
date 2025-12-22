# AI Tax Intelligence

Automated extraction of financial evidence from SEC 10-K filings for tax method change analysis.

## Project Structure

```
ai-tax-intelligence/
├── src/                    # Python extraction engine
│   ├── stage1_parser.py    # PDF parsing and section detection
│   ├── stage2_verbatim.py  # LLM-powered evidence extraction (main)
│   ├── stage3_summary.py   # Evidence summarization (optional)
│   └── stage4_excel.py     # Excel output generation
├── terraform/              # AWS infrastructure (EC2, n8n, Caddy SSL)
├── n8n/                    # Workflow automation configs
├── Dockerfile              # Container for extraction engine
└── requirements.txt        # Python dependencies
```

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set API key
export ANTHROPIC_API_KEY='your-key-here'

# Run extraction
cd src
python stage2_verbatim.py /path/to/10K.pdf
```

### Output

The extraction produces:
- `{filename}_extraction.json` - Structured evidence data
- Evidence includes: verbatim quotes, page numbers, confidence levels, verification status

## Extraction Architecture

### Two-Stage Pipeline

1. **Stage 1: Deterministic Parsing** (`stage1_parser.py`)
   - PDF text extraction using pdfplumber
   - Section detection (Notes, MD&A, Financial Statements)
   - Page number tracking

2. **Stage 2: LLM Extraction** (`stage2_verbatim.py`)
   - Block-chunking architecture (6 API calls per document)
   - Relevance-scored chunk selection
   - Verbatim quote extraction with verification

### Blocks & Categories

| Block | Categories |
|-------|------------|
| **Fixed Assets** | Depreciation, Intangibles, PP&E, Repair & Maintenance, Spare Parts, Building, M&A, Expansion |
| **Inventory** | Inventory (LIFO/FIFO/UNICAP) |
| **R&D** | Research & Development |
| **Tax** | Section 163(j), Deferred Tax, Prepaid Expense, Deferred Revenue, Advanced Payments, Revenue Recognition |
| **Financial Statements** | Income Statement, Balance Sheet, Cash Flow |
| **Business Overview** | Business Description |

### Key Features

- **Relevance-Scored Chunking**: Prioritizes chunks with financial specifics (dollar amounts, dates) over generic language
- **Verbatim Extraction**: Exact quotes only, never paraphrased
- **Page Number Tracking**: Every quote includes source page
- **Verification**: Post-extraction check that quotes exist in source document
- **Cost Control**: ~$0.25-0.35 per document using Claude Sonnet

## Configuration

### Using Custom Configuration Files (Recommended)

**No code editing needed!** Customize prompts and keywords via JSON config files:

```bash
# Create your custom config
cp config/default_config.json config/my_config.json

# Edit keywords, prompts, model settings
vim config/my_config.json

# Use it
python run.py extract company_10K.pdf --config config/my_config.json
```

**What you can customize:**
- System and user prompts (evidence length, confidence criteria)
- Keywords and categories for your industry
- Model selection (Sonnet vs Opus)
- Priority sections to search

**Examples:**
- [config/custom_example.json](config/custom_example.json) - Tech/crypto company focus
- [config/README.md](config/README.md) - Full configuration guide

### Legacy: Editing Python Code Directly

If you prefer to edit Python (not recommended):

Edit `BLOCKS` in `stage2_verbatim.py`:

```python
"New Category": [
    "keyword1", "keyword2", "specific phrase"
]
```

**Note:** Using config files is preferred because:
- ✅ No code changes needed
- ✅ Easy to test different configurations
- ✅ Version control for prompts
- ✅ Share configs across team
- ✅ Works seamlessly with n8n

## AWS Deployment (Optional)

```bash
cd terraform

# Configure
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars

# Deploy
terraform init
terraform apply
```

Creates: EC2 instance with n8n workflow automation, Caddy SSL, extraction engine.

## API Usage

### Environment Variables

```bash
ANTHROPIC_API_KEY=sk-ant-...  # Required
```

### Python API

```python
from stage1_parser import parse_document
from stage2_verbatim import VerbatimExtractor

# Parse PDF
doc = parse_document("company_10K.pdf")

# Extract evidence
extractor = VerbatimExtractor()
result = extractor.extract(doc, "company_10K")

# Access results
for extraction in result.extractions:
    print(f"{extraction.category}: {len(extraction.evidence)} items")
    for ev in extraction.evidence:
        print(f"  Page {ev.page}: {ev.text[:100]}...")
```

## Cost Estimates

| Document Size | API Cost | Processing Time |
|---------------|----------|-----------------|
| ~100 pages | $0.25-0.30 | ~60 seconds |
| ~150 pages | $0.30-0.40 | ~90 seconds |

Costs based on Claude Sonnet pricing: $3/M input, $15/M output tokens.

## Golden Standard Documents

Tested against:
- Bristow Group (98 pages) - Helicopter services
- Transocean (118 pages) - Offshore drilling
- LYB (LyondellBasell) - Petrochemicals
- Molson Coors - Beverages

## License

MIT
