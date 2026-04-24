# HÜMÄNIẞAHHH

Strips LLM fingerprints from text. Rewrites AI-generated prose to read as authentically human-written — removes hedging language, em dashes, over-structured bullets, filler openers, and other telltale patterns. Preserves all original meaning, facts, and sentential logic.

## Features

- Matter-of-fact voice: no opinion, no slang, no first-person additions
- Input-grounded language: never introduces vocabulary not in the original
- Sentential logic preservation: causality, conditionals, negation, and hedge level all intact
- Multi-pass rewriting: structural, perplexity, and burstiness passes available via web UI
- Subtle error injection to break statistical AI signatures

## Usage

```bash
# Web UI
./start.sh
# open http://localhost:5757

# CLI — rewrites a file (saves to input_humanized.txt)
python3 humanize.py input.txt

# CLI — specify output path
python3 humanize.py input.txt output.txt
```

## Stack

- Python 3, Flask, `anthropic` SDK
- All prompt logic in `prompt.py` — edit there to update all passes

## Setup

```bash
pip install anthropic flask python-docx
cp start.sh.example start.sh   # add your key
chmod +x start.sh
./start.sh
```

> `start.sh` is gitignored — it contains your API key.
