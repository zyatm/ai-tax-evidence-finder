# Quick Start: Custom Configuration

Get started with custom configurations in 5 minutes.

## Step 1: Copy the Default Config (30 seconds)

```bash
cd /Users/zaid/Projects/ai-tax-evidence-finder
cp config/default_config.json config/my_custom.json
```

## Step 2: Edit Keywords for Your Industry (2 minutes)

Open `config/my_custom.json` in any text editor and modify the keywords:

### Example: Add Cryptocurrency Keywords

Find the "Fixed Assets" block and add a new category:

```json
{
  "blocks": {
    "Fixed Assets": {
      "categories": {
        "Depreciation/Amortization": [...],
        "Digital Assets": [
          "cryptocurrency",
          "bitcoin",
          "ethereum",
          "digital currency",
          "crypto assets",
          "blockchain technology"
        ]
      }
    }
  }
}
```

### Example: Modify Tax Keywords

Find the "Tax" block and add industry-specific terms:

```json
{
  "blocks": {
    "Tax": {
      "categories": {
        "Stock-Based Compensation": [
          "RSU",
          "restricted stock units",
          "stock options",
          "equity compensation",
          "employee stock purchase plan",
          "ESPP"
        ]
      }
    }
  }
}
```

## Step 3: Test Your Config (2 minutes)

```bash
# Set your API key
export ANTHROPIC_API_KEY='your-key-here'

# Run with your custom config
python run.py extract your_10K.pdf --config config/my_custom.json
```

Look for this in the output:
```
[Config] Loading custom configuration from: config/my_custom.json
[Config] Using model: claude-sonnet-4-20250514
[Config] Loaded 6 blocks
```

## Step 4: Review Results (1 minute)

Open the generated Excel file and check:
- ✅ Are your new keywords finding relevant evidence?
- ✅ Is the evidence length appropriate?
- ✅ Are you getting the categories you need?

## Done! 🎉

You now have a custom configuration tailored to your needs.

---

## Common Quick Edits

### Make Evidence Longer
Find `"system_prompt"` and change:
```json
"7) LENGTH: Each evidence quote should typically be 2-8 sentences..."
```

### Make Evidence Shorter
```json
"7) LENGTH: Each evidence quote should typically be 1-2 sentences..."
```

### Remove Unnecessary Categories
Just delete categories you don't need:
```json
{
  "blocks": {
    "Tax": {
      "categories": {
        "Section 163(j)": [...],
        "Deferred Tax (DTL/DTA)": [...]
        // Removed other categories
      }
    }
  }
}
```

### Switch to Opus (More Accurate, More Expensive)
```json
{
  "model": {
    "name": "claude-opus-4-5-20251101",
    "input_cost_per_m": 15.00,
    "output_cost_per_m": 75.00
  }
}
```

---

## Pro Tips

**Tip 1:** Start with `custom_example.json` if you're in tech
```bash
python run.py extract tech_10K.pdf --config config/custom_example.json
```

**Tip 2:** Test on a small section first
Edit your config to only include 1-2 blocks, test, then expand.

**Tip 3:** Keep backups
```bash
cp config/my_custom.json config/my_custom_backup.json
```

**Tip 4:** Use descriptive names
```bash
config/oil_and_gas_focus.json
config/tech_companies.json
config/manufacturing_detailed.json
```

---

## Need More Help?

- Full guide: [config/README.md](config/README.md)
- Implementation details: [CONFIGURATION_SUMMARY.md](CONFIGURATION_SUMMARY.md)
- Examples: [config/custom_example.json](config/custom_example.json)
