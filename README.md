# Humanizer

CLI tool that strips LLM fingerprints from text files via Claude API. Rewrites AI-generated prose to read naturally — removes hedging language, em dashes, over-structured bullet points, and other telltale patterns.

## Usage

```bash
# Rewrite a file (saves to input_humanized.txt)
python3 humanize.py input.txt

# Specify output path
python3 humanize.py input.txt output.txt

# Local HTTP server (POST /humanize with {"text": "..."})
python3 humanize_server.py
```

## Stack

- Python 3, `anthropic` SDK
- System prompt in `prompt.py`

## Setup

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-...
python3 humanize.py myfile.txt
```
