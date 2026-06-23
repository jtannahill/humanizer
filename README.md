# Humanizer

![Status](https://img.shields.io/badge/status-active-success)
![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?logo=flask&logoColor=white)
![Claude](https://img.shields.io/badge/Claude-D97757?logo=anthropic&logoColor=white)
![Last Commit](https://img.shields.io/github/last-commit/jtannahill/humanizer)

Strips LLM fingerprints from text. Rewrites AI-generated prose to read as authentically human-written: removes hedging language, em dashes, over-structured bullets, filler openers, and other telltale patterns. Preserves all original meaning, facts, and sentential logic.

## Features

- Matter-of-fact voice: no opinion, no slang, no first-person additions
- Input-grounded language: never introduces vocabulary not in the original
- Sentential logic preservation: causality, conditionals, negation, and hedge level all intact
- Multi-pass rewriting: structural, perplexity, sentence, and nuclear (fact-extract → rewrite-from-scratch) passes
- Nuclear rewrite is on by default and runs first in the loop; output capped at +20% of original word count
- Combined-oracle loop: tracks best output by `0.7 × GPTZero + 0.3 × (1 − local_human_score)`; final badge still reports the GPTZero number
- Subtle error injection to break statistical AI signatures
- Pluggable local detector (oracle): GPT-2 perplexity, Binoculars (Qwen3-1.7B), or Fast-DetectGPT (Qwen3-1.7B)
- Prompt caching on the main system prompt (1h TTL) to keep API cost down on repeat runs
- Explicit `temperature=1.0` on all Claude calls (Anthropic's max) for documented sampling behavior

## Architecture

Humanizer is self-hosted. The Flask app and the local detector models run on a single Mac; the public hostname is fronted by a Cloudflare Tunnel. There is no separate frontend build, no database, and no server-side session state: the whole UI is one HTML/JS string served from `/`, and all run state lives in the browser.

### Deployment topology

```mermaid
flowchart LR
    U["Browser<br/>humanizer.jamestannahill.com"]
    CF["Cloudflare edge"]
    T["cloudflared tunnel"]
    F["Flask app<br/>humanize_server.py<br/>127.0.0.1:5757"]
    A["Anthropic API (Claude)"]
    G["GPTZero API"]
    L["Local detector (in-process)<br/>GPT-2 / Binoculars / Fast-DetectGPT"]

    U -->|HTTPS| CF -->|tunnel| T --> F
    F -->|messages.stream| A
    F -->|POST /detect| G
    F -.in-process.-> L
```

The tunnel maps `humanizer.jamestannahill.com` to `http://127.0.0.1:5757`. Outbound calls to the Anthropic and GPTZero APIs originate from the same machine, and the local detectors run in-process via `scorer.py`. If the Mac is offline, the site is down.

### Request lifecycle

A single HUMANIZE click drives an initial streamed rewrite followed by a measure-and-rewrite loop:

```mermaid
flowchart TD
    P["Paste text, click HUMANIZE"] --> H["POST /humanize (streamed)<br/>Pass 1: SYSTEM_PROMPT rewrite<br/>Pass 2: PASS2_PROMPT burstiness"]
    H --> S["autoScanOutput()"]
    S --> D1["POST /detect (GPTZero, cloud)"]
    S --> D2["POST /local-score (local oracle)"]
    D1 --> C["combined = 0.7 x GPTZero + 0.3 x (1 - local_human_score)"]
    D2 --> C
    C --> B{"loopCount under MAX_LOOPS (4)?"}
    B -->|yes| R["rehumanizeLoop(): rotate one strategy per pass<br/>1 nuclear, 2 sentence, 3 perplexity, 4 structural<br/>then programmatic_burstiness()"]
    R --> S
    B -->|no| BEST["restore best-scoring version<br/>report GPTZero human %"]
```

Running states, in order:

1. **Initial rewrite.** `/humanize` streams Claude output token by token. With 2-pass on (default), Pass 1 rewrites under `SYSTEM_PROMPT`, then a `\f---PASS2---\f` sentinel tells the browser to clear and Pass 2 re-runs the text under `PASS2_PROMPT` for burstiness. Every chunk is cleaned server-side (em/en dashes to commas, markdown bold stripped).
2. **Auto-scan.** The output is scored by two detectors in parallel: GPTZero (`/detect`, cloud) and a local oracle (`/local-score`, on-device). They combine as `0.7 x GPTZero + 0.3 x (1 - local_human_score)`, with GPTZero as primary and the local model as a guard rail.
3. **Rehumanize loop.** Up to `MAX_LOOPS` (4) iterations, rotating one strategy per pass: nuclear rewrite, sentence rewrite, perplexity injection, structural rewrite. Each strategy's output is run through `programmatic_burstiness()`, a non-LLM pass that merges short sentences and splits long ones, then re-scanned.
4. **Best-of finish.** The lowest combined-score version is retained across all iterations and restored at the end if the final pass regressed. The badge reports the GPTZero human percentage of that best version.

### HTTP endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Single-page UI (HTML/CSS/JS) |
| POST | `/humanize` | Streamed initial rewrite (1 or 2 pass) |
| POST | `/detect` | GPTZero proxy (cloud) |
| POST | `/local-score` | Local detector (`gpt2` / `binoculars` / `fast_detectgpt`) |
| POST | `/nuclear-rewrite` | Loop strategy 1: fact-extract then rewrite from scratch |
| POST | `/rehumanize-sentences` | Loop strategy 2: rewrite GPTZero-flagged sentences |
| POST | `/perplexity-inject` | Loop strategy 3: lower-probability word swaps |
| POST | `/structural-rewrite` | Loop strategy 4: full-document restructure |
| POST | `/export` | Download current output as `.docx` |
| GET | `/favicon.svg`, `/favicon.ico` | Brand favicon |

## Usage

```bash
# Web UI
./start.sh
# open http://localhost:5757

# CLI: rewrites a file (saves to input_humanized.txt)
python3 humanize.py input.txt

# CLI: specify output path
python3 humanize.py input.txt output.txt
```

## Stack

- Python 3.10+, Flask, `anthropic` SDK
- All prompt logic in `prompt.py`: edit there to update all passes
- Local detectors in `scorer.py` (dispatcher), `binoculars_scorer.py`, `fast_detectgpt_scorer.py`
- GPT-2 and Binoculars run on PyTorch+MPS; Fast-DetectGPT runs on MLX (Apple Silicon native, bf16). Weights download to the HuggingFace cache on first use: separate cache slots for the PyTorch (`Qwen/Qwen3-1.7B-Base`, `Qwen/Qwen3-1.7B`) and MLX (`mlx-community/Qwen3-1.7B-bf16`) variants.

## Detector backends

Switch via the dropdown in the header. The selected backend feeds the loop oracle alongside GPTZero (70% GPTZero / 30% local). Thresholds in `binoculars_scorer.py` and `fast_detectgpt_scorer.py` are rough starting points: calibrate on a real corpus before trusting the numeric `human_score`.

| Backend | Runtime | Model | Memory | Warm latency | Notes |
|---|---|---|---|---|---|
| `gpt2` | PyTorch+MPS | GPT-2 large | ~2GB | ~150ms | Default; fastest cold-start; weakest signal |
| `binoculars` | PyTorch+MPS | Qwen3-1.7B-Base + Qwen3-1.7B (pair) | ~7GB | ~300ms | Stronger signal; closer to paper-quality |
| `fast_detectgpt` | MLX (bf16) | Qwen3-1.7B | ~3.4GB | ~80–140ms | Single model, often beats Binoculars on out-of-distribution text |

> **Pick one backend per session.** Each backend lazy-loads its weights on first use and stays resident. Switching mid-session leaves all selected backends in unified memory; on a 16GB Mac, GPT-2 + Binoculars + Fast-DetectGPT together (~12GB) will trigger heavy swap. Restart the server to flush.

## Loop strategy rotation

When you click HUMANIZE the loop runs up to 4 iterations, rotating through these strategies:

1. **Nuclear** (default on): extract every fact, claim, number, name, date as a bullet list, then write fresh prose from those bullets. Most fingerprint-breaking pass. Hard-capped at +20% of original word count (prompt + post-processing).
2. **Sentence rewrite**: rewrites only sentences flagged by GPTZero, with diagnostic context (burstiness, paraphrased vs. pure-AI subclass) baked into the prompt.
3. **Perplexity injection**: replaces high-probability words with lower-probability but natural alternatives in flagged sentences.
4. **Structural rewrite**: full-document restructure: clause reordering, paragraph splits/merges, sentence-length extremes for burstiness.

The loop tracks the lowest combined-oracle score across all iterations and restores that version at the end if the final pass regressed. The final status line and score badge always show the GPTZero score for the best output, since that's the user-facing number.

Toggle nuclear off (header button) to fall back to the 3-strategy rotation.

## Setup

```bash
uv sync                       # installs from pyproject.toml + uv.lock
cp start.sh.example start.sh  # add your ANTHROPIC_API_KEY (or use a .env file)
chmod +x start.sh
./start.sh
```

> `start.sh` is gitignored: it contains your API key. The `mlx` and `mlx-lm` deps are Apple Silicon only; on non-Mac hosts `uv sync` will fail there. Fast-DetectGPT is the only backend that requires them.

## Tests

```bash
uv run pytest tests/ -v       # parity tests (~30s warm, ~2 min cold)
uv run python scripts/bench_scorers.py  # warm-call latency per backend
```
