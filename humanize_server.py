#!/usr/bin/env python3
"""
humanize_server.py - Local web UI for the humanizer.

Usage:
    python3 humanize_server.py
    open http://localhost:5757
"""

import os
import anthropic
from flask import Flask, Response, request, stream_with_context
from prompt import SYSTEM_PROMPT

app = Flask(__name__)


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Humanizer</title>
<link href="https://fonts.googleapis.com/css2?family=Courier+Prime:ital,wght@0,400;0,700;1,400&family=Bebas+Neue&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --ink: #1a1610;
    --paper: #f4f0e8;
    --paper-dark: #e8e2d4;
    --rule: #c8bfa8;
    --red: #c0392b;
    --red-hover: #a93226;
    --muted: #7a6e5e;
    --mono: 'Courier Prime', 'Courier New', monospace;
    --display: 'Bebas Neue', sans-serif;
  }

  body {
    background: var(--paper);
    color: var(--ink);
    font-family: var(--mono);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  /* noise texture overlay */
  body::before {
    content: '';
    position: fixed;
    inset: 0;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E");
    pointer-events: none;
    z-index: 100;
    opacity: 0.6;
  }

  header {
    border-bottom: 3px double var(--ink);
    padding: 18px 32px 14px;
    display: flex;
    align-items: baseline;
    gap: 20px;
  }

  .logo {
    font-family: var(--display);
    font-size: 2.4rem;
    letter-spacing: 0.06em;
    color: var(--ink);
    line-height: 1;
  }

  .tagline {
    font-size: 0.72rem;
    color: var(--muted);
    letter-spacing: 0.12em;
    text-transform: uppercase;
    border-left: 1px solid var(--rule);
    padding-left: 16px;
    line-height: 1.4;
  }

  main {
    flex: 1;
    display: grid;
    grid-template-columns: 1fr 1fr;
    grid-template-rows: auto 1fr;
    gap: 0;
  }

  .col-header {
    border-bottom: 1px solid var(--rule);
    padding: 10px 24px;
    font-size: 0.65rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--muted);
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .col-header:first-child {
    border-right: 1px solid var(--rule);
  }

  .word-count {
    font-size: 0.62rem;
    color: var(--rule);
    font-variant-numeric: tabular-nums;
  }

  .pane {
    position: relative;
    height: calc(100vh - 120px);
  }

  .pane:first-of-type {
    border-right: 1px solid var(--rule);
  }

  .pane.drag-over {
    background: rgba(192, 57, 43, 0.04);
    outline: 2px dashed var(--red);
    outline-offset: -8px;
  }

  .drop-hint {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.15s;
    font-size: 0.72rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--red);
  }

  .pane.drag-over .drop-hint {
    opacity: 1;
  }

  textarea {
    width: 100%;
    height: 100%;
    background: transparent;
    border: none;
    outline: none;
    resize: none;
    font-family: var(--mono);
    font-size: 0.88rem;
    line-height: 1.75;
    color: var(--ink);
    padding: 24px;
    caret-color: var(--red);
  }

  textarea::placeholder {
    color: var(--rule);
    font-style: italic;
  }

  #output {
    background: transparent;
    cursor: default;
  }

  #output.streaming {
    color: var(--ink);
  }

  .toolbar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: var(--paper-dark);
    border-top: 2px solid var(--ink);
    padding: 12px 32px;
    display: flex;
    align-items: center;
    gap: 16px;
    z-index: 10;
  }

  #run-btn {
    font-family: var(--display);
    font-size: 1rem;
    letter-spacing: 0.12em;
    background: var(--red);
    color: var(--paper);
    border: none;
    padding: 9px 28px 7px;
    cursor: pointer;
    transition: background 0.15s;
    outline: none;
  }

  #run-btn:hover { background: var(--red-hover); }
  #run-btn:disabled { background: var(--rule); cursor: not-allowed; }

  #copy-btn {
    font-family: var(--mono);
    font-size: 0.72rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    background: transparent;
    color: var(--muted);
    border: 1px solid var(--rule);
    padding: 7px 16px;
    cursor: pointer;
    transition: all 0.15s;
  }

  #copy-btn:hover { border-color: var(--ink); color: var(--ink); }
  #copy-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  #clear-btn {
    font-family: var(--mono);
    font-size: 0.72rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    background: transparent;
    color: var(--muted);
    border: 1px solid transparent;
    padding: 7px 16px;
    cursor: pointer;
    transition: all 0.15s;
  }

  #clear-btn:hover { border-color: var(--rule); }

  #status {
    margin-left: auto;
    font-size: 0.68rem;
    letter-spacing: 0.1em;
    color: var(--muted);
    font-style: italic;
  }

  .cursor-blink {
    display: inline-block;
    width: 0.5em;
    height: 1em;
    background: var(--red);
    animation: blink 0.8s step-end infinite;
    vertical-align: text-bottom;
    margin-left: 2px;
  }

  @keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
  }

  /* rule lines in textarea panes */
  .pane::after {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    background-image: repeating-linear-gradient(
      transparent,
      transparent calc(1.75em * 0.88rem / 1rem + 24px - 1px),
      rgba(200,191,168,0.18) calc(1.75em * 0.88rem / 1rem + 24px)
    );
    background-size: 100% calc(1.75 * 0.88rem);
    background-position: 0 24px;
    pointer-events: none;
  }
</style>
</head>
<body>

<header>
  <div class="logo">Humanizer</div>
  <div class="tagline">strip AI fingerprints<br>from your prose</div>
</header>

<main>
  <div class="col-header">
    Input
    <span class="word-count" id="in-count">0 words</span>
  </div>
  <div class="col-header">
    Output
    <span class="word-count" id="out-count">-</span>
  </div>

  <div class="pane" id="input-pane">
    <textarea id="input" placeholder="Paste your text here...&#10;&#10;The more LLM-ish, the better."></textarea>
    <div class="drop-hint">Drop .txt file</div>
  </div>

  <div class="pane">
    <textarea id="output" readonly placeholder="Humanized output will appear here..."></textarea>
  </div>
</main>

<div class="toolbar">
  <button id="run-btn">HUMANIZE</button>
  <button id="copy-btn" disabled>COPY</button>
  <button id="clear-btn">CLEAR</button>
  <span id="status"></span>
</div>

<script>
const inputEl  = document.getElementById('input');
const outputEl = document.getElementById('output');
const runBtn   = document.getElementById('run-btn');
const copyBtn  = document.getElementById('copy-btn');
const clearBtn = document.getElementById('clear-btn');
const status   = document.getElementById('status');
const inCount  = document.getElementById('in-count');
const outCount = document.getElementById('out-count');

function countWords(str) {
  return str.trim() ? str.trim().split(/\s+/).length : 0;
}

inputEl.addEventListener('input', () => {
  inCount.textContent = countWords(inputEl.value) + ' words';
});

clearBtn.addEventListener('click', () => {
  inputEl.value = '';
  outputEl.value = '';
  inCount.textContent = '0 words';
  outCount.textContent = '-';
  copyBtn.disabled = true;
  status.textContent = '';
});

copyBtn.addEventListener('click', async () => {
  await navigator.clipboard.writeText(outputEl.value);
  copyBtn.textContent = 'COPIED';
  setTimeout(() => copyBtn.textContent = 'COPY', 1500);
});

runBtn.addEventListener('click', async () => {
  const text = inputEl.value.trim();
  if (!text) return;

  runBtn.disabled = true;
  copyBtn.disabled = true;
  outputEl.value = '';
  outCount.textContent = '-';
  status.textContent = 'processing...';

  try {
    const res = await fetch('/humanize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });

    if (!res.ok) {
      const err = await res.json();
      status.textContent = 'error: ' + (err.error || res.statusText);
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let full = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      full += chunk;
      outputEl.value = full;
      outCount.textContent = countWords(full) + ' words';
      outputEl.scrollTop = outputEl.scrollHeight;
    }

    status.textContent = 'done';
    copyBtn.disabled = false;

  } catch (e) {
    status.textContent = 'error: ' + e.message;
  } finally {
    runBtn.disabled = false;
  }
});

// cmd+enter / ctrl+enter to run
inputEl.addEventListener('keydown', e => {
  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
    runBtn.click();
  }
});

// drag & drop txt files onto input pane
const inputPane = document.getElementById('input-pane');

inputPane.addEventListener('dragenter', e => {
  e.preventDefault();
  inputPane.classList.add('drag-over');
});

inputPane.addEventListener('dragover', e => {
  e.preventDefault();
  e.dataTransfer.dropEffect = 'copy';
});

inputPane.addEventListener('dragleave', e => {
  if (!inputPane.contains(e.relatedTarget)) {
    inputPane.classList.remove('drag-over');
  }
});

inputPane.addEventListener('drop', e => {
  e.preventDefault();
  inputPane.classList.remove('drag-over');

  const file = e.dataTransfer.files[0];
  if (!file) return;

  if (!file.name.endsWith('.txt') && file.type !== 'text/plain') {
    status.textContent = 'only .txt files supported';
    return;
  }

  const reader = new FileReader();
  reader.onload = ev => {
    inputEl.value = ev.target.result;
    inCount.textContent = countWords(inputEl.value) + ' words';
    status.textContent = 'loaded: ' + file.name;
  };
  reader.readAsText(file);
});
</script>
</body>
</html>"""


@app.route("/")
def index():
    return HTML


@app.route("/humanize", methods=["POST"])
def humanize():
    data = request.get_json()
    text = (data or {}).get("text", "").strip()
    if not text:
        return {"error": "no text provided"}, 400

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY not set"}, 500

    client = anthropic.Anthropic(api_key=api_key)

    def generate():
        with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Humanize the following text:\n\n{text}"}]
        ) as stream:
            for chunk in stream.text_stream:
                yield chunk.replace("\u2014", ",").replace("**", "")

    return Response(stream_with_context(generate()), mimetype="text/plain")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5757))
    print(f"Humanizer running at http://localhost:{port}")
    print("Press Ctrl+C to stop.\n")
    app.run(port=port, debug=False)
