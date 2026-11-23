# Document PII Redactor

A Python tool that extracts text from documents (.txt, .pdf, .docx) and permanently redacts Personally Identifiable Information (PII) such as Names, Addresses, Emails, Phone Numbers, and GST Numbers.

## Key Features

- **Multi-format Support**: Extracts text from PDFs, Word Documents, and text files.
- **Robust NLP Engine**: Uses Microsoft Presidio and spaCy for accurate entity recognition.
- **Offline Processing**: All text analysis and redaction happens locally without making API calls.
- **Customizable**: Edit `config.yml` to specify which PII entities you want to redact.
- **Custom Patterns**: Includes support for Indian GST numbers.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# 2. Add your documents (.pdf, .docx, .txt) to data/input/
# Note: Ensure the directory exists or the script will create it on first run.

# 3. Run the redactor
python src/redact_documents.py
```

## ⚙️ Configuration

Edit `config.yml` to customize behavior:

```yaml
paths:
  input_dir: "./data/input/"
  output_dir: "./data/output/"

redaction:
  entities:
    - PERSON
    - EMAIL_ADDRESS
    - PHONE_NUMBER
    - IN_PAN
    - IN_GST
    - LOCATION
```

## File Structure

```
bank_statement_extractor/
├── src/
│   ├── redact_documents.py       # Main redaction pipeline
├── data/
│   ├── input/                    # Place files to be redacted here
│   └── output/                   # Processed redacted text files
├── config.yml                    # Configuration settings
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

## Supported PII Entities

By default, the tool redacts:
- `PERSON` (Names)
- `EMAIL_ADDRESS`
- `PHONE_NUMBER`
- `LOCATION` (Addresses)
- `IN_PAN` (Indian PAN numbers)
- `IN_GST` (Custom recognizer for Indian GST numbers)

Financial data like transaction amounts or bank balances are intentionally *not* redacted by default, so you can still perform financial analysis on the redacted output.