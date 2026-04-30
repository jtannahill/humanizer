# HÜMÄNIẞAHHH

Strips LLM fingerprints from text. Rewrites AI-generated prose to read as authentically human-written — removes hedging language, em dashes, over-structured bullets, filler openers, and other telltale patterns. Preserves all original meaning, facts, and sentential logic.

## Features

- Matter-of-fact voice: no opinion, no slang, no first-person additions
- Input-grounded language: never introduces vocabulary not in the original
- Sentential logic preservation: causality, conditionals, negation, and hedge level all intact
- Multi-pass rewriting: structural, perplexity, and burstiness passes available via web UI
- Subtle error injection to break statistical AI signatures
- Pluggable local detector (oracle): GPT-2 perplexity, Binoculars (Qwen 2.5-1.5B), or Fast-DetectGPT (Qwen 2.5-1.5B)
- Prompt caching on the main system prompt (1h TTL) to keep API cost down on repeat runs

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
- Local detectors in `scorer.py` (dispatcher), `binoculars_scorer.py`, `fast_detectgpt_scorer.py`
- First use of a Qwen-backed detector downloads `Qwen/Qwen2.5-1.5B` (~3GB) to the HuggingFace cache; both Binoculars and Fast-DetectGPT share it

## Detector backends

Switch via the dropdown in the header. Thresholds in `binoculars_scorer.py` and `fast_detectgpt_scorer.py` are rough starting points — calibrate on a real corpus before trusting the numeric `human_score`.

| Backend | Model | Memory | When to use |
|---|---|---|---|
| `gpt2` | GPT-2 large | ~2GB | Default; fastest; weakest signal |
| `binoculars` | Qwen 2.5-1.5B + Instruct (pair) | ~6GB | Stronger signal; closer to paper-quality |
| `fast_detectgpt` | Qwen 2.5-1.5B | ~3GB | Single-model, often beats Binoculars on out-of-distribution text |

## Setup

```bash
pip install anthropic flask python-docx
cp start.sh.example start.sh   # add your key
chmod +x start.sh
./start.sh
```

> `start.sh` is gitignored — it contains your API key.
