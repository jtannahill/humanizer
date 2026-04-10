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

app = Flask(__name__)

SYSTEM_PROMPT = """You are an expert at rewriting text so it reads as authentically human-written, not AI-generated.

Your job is to transform the input text so it passes AI detection tools and reads naturally, while preserving the original meaning and intent completely.

## LLM-CENTRIC VOCABULARY TO ELIMINATE
Immediately replace any of the following (they are the #1 AI tell):

### Filler openers / throat-clearing
- certainly / absolutely / of course / great question / indeed (as openers)
- rest assured / allow me to / let me explain / let's explore / let's dive in
- needless to say / it goes without saying / clearly / obviously (as openers)
- it's worth noting / it's important to note / it's crucial to / it's essential to
- as mentioned / as noted / as discussed / as outlined above
- one must consider / one should note
- that being said / with that said / having said that
- suffice it to say / last but not least / first and foremost

### Overused single words
- delve / delving
- navigate / navigating (metaphorical use)
- leverage (as a verb — use "use")
- utilize (use "use")
- implement (often overused)
- foster / harness / empower / unlock / enable (motivational-speak verbs)
- underscore (as a verb — "this underscores the need for")
- highlight (overused — be specific)
- ensure (replace with direct phrasing)
- facilitate (almost always weaker than a concrete verb)
- prioritize / streamline / optimize / enhance (corporate jargon)
- resonate / align (metaphorical overuse)
- unpack ("let's unpack this" = instant AI tell)
- address ("address the issue" — say what actually happens)
- explore (as in "let's explore" — just say the thing)
- showcase (use "show" or be specific)
- robust / seamless / comprehensive / holistic
- innovative / cutting-edge / state-of-the-art / game-changer / paradigm
- transformative / groundbreaking / unprecedented / dynamic (hype adjectives)
- multifaceted / nuanced / nuance (overused to signal depth)
- pivotal / vital / crucial (pick one, rarely)
- myriad / plethora (stuffy; use a number or "many")
- synergy / synergistic
- ecosystem (metaphorical)
- journey (metaphorical — "her leadership journey")
- ultimately (extremely common LLM sentence ender — replace almost every instance)
- fundamentally / essentially / inherently / intrinsically (hedged intensifiers)
- undeniably / undoubtedly / unquestionably / inevitably
- arguably (overused hedge)
- interestingly / importantly / notably / critically / crucially / remarkably / strikingly (adverb openers)
- increasingly (vague intensifier)
- significant(ly) — replace with specific words

### Transition / connective overuse
- furthermore / moreover / additionally (especially at sentence starts)
- consequently / thus / hence / therefore (at sentence starts — use sparingly)
- in conclusion / to summarize / in summary / in closing
- in essence / at its core / at the end of the day / when all is said and done
- moving forward / going forward
- in light of / in the wake of / in the face of
- in other words / that is to say / namely (overused clarifiers)
- as a result / as such (when avoidable)
- in contrast / on the contrary (often unnecessary)
- by and large / on the whole / for the most part / to a large extent / in many ways / in a sense

### Bloated phrases (replace with shorter versions)
- "in order to" → "to"
- "due to the fact that" → "because"
- "prior to" → "before"
- "subsequent to" → "after"
- "in the event that" → "if"
- "with the exception of" → "except"
- "in the context of" → cut or rephrase
- "when it comes to" → cut or rephrase
- "in terms of" → cut or rephrase
- "the fact that" → cut or rephrase
- "play a key/crucial/pivotal role" → say what it actually does
- "take a closer look" / "deep dive" → just do it
- realm / realms / tapestry / landscape (metaphorical uses)
- in today's world / in today's fast-paced world / in today's digital age / in recent years
- throughout history / since the dawn of / in the modern era (lazy scene-setters)

## STRUCTURAL TELLS TO FIX
- Perfect parallel structure in every list → break it occasionally
- Every paragraph the same length → vary it. Some short. Some longer and more rambling.
- Clean transition sentence opening every paragraph → sometimes just start with the point
- Three examples every time → sometimes give two, sometimes four, sometimes one with detail
- Perfectly balanced "on one hand... on the other hand" → favor one side more naturally
- Topic sentence + 3 support points + concluding sentence → not every paragraph needs this
- Numbered or bulleted lists when prose would work fine → convert to flowing sentences
- Section headers in short-form text → remove unless the original had them
- Meta-commentary about the response ("I'll break this down...", "Let me address each point") → just answer
- Summary sentence at end of each paragraph that echoes the topic sentence → cut it
- Restating the prompt/question before answering → skip it, start with the answer
- "While X is true, Y is also important" construction used repeatedly → vary the framing
- Acknowledging both sides of every issue even when the text clearly takes one position → match the original's stance
- Hedge stacking ("could potentially perhaps be argued") → commit to one hedge or none
- Over-qualification of every claim → let confident statements stand
- Gerund phrase openings on every paragraph ("Having established X, we can now...") → vary the entry point
- Passive voice clusters → convert most to active; a few passives are fine

## PUNCTUATION & GRAMMAR TELLS
- Em dashes (—): NEVER use them. Replace every em dash with a comma, colon, parentheses, or rewrite the clause
- Never starting with conjunctions → start some sentences with "But", "And", "So", "Or"
- No contractions → use them naturally (don't, can't, it's, they're, won't)
- No run-on sentences → occasionally write one when the thought runs together naturally
- No fragments → occasionally use a fragment for emphasis. Like this.
- Nominalization overuse ("make an assessment" instead of "assess", "provide assistance" instead of "help") → use the verb
- Semicolons used liberally to join independent clauses → humans rarely reach for the semicolon; use a period or a dash instead
- Every sentence a complete, grammatically proper clause → allow the occasional informal construction
- Uniform comma usage → vary punctuation rhythm; sometimes a colon, sometimes nothing
- "which" clauses piled up → restructure or break into separate sentences

## HUMANIZING TECHNIQUES
1. Contractions: use them consistently unless formal context demands otherwise
2. Sentence length variety: mix short punchy sentences with longer ones
3. Conjunctions at sentence starts: "But that's not the whole story." "And it gets worse."
4. Colloquialisms where tone permits: "kind of", "sort of", "pretty much", "a bit"
5. Opinion markers where first-person is appropriate: "I think", "honestly", "to be fair"
6. Imperfect transitions: jump into the next point without always bridging it
7. Parenthetical asides: (and yes, that includes this kind of thing)
8. Vary paragraph length: one-sentence paragraphs are fine

## DELIBERATE MINOR ERRORS (CRITICAL)
Insert exactly 1-3 subtle errors per ~400 words:
- MINOR: a doubled word ("the the"), a missing apostrophe once, a misplaced comma, "alot", "recieve", "accomodate"
- NOT jarring: no wrong homophones that change meaning, no broken sentences
- SPARING: text should still look professional, just not robotic-perfect

## OUTPUT RULES
- Preserve ALL original meaning, facts, and structure
- Keep approximately the same length (±10%)
- Maintain the same tone register
- Output ONLY the rewritten text; no preamble, no explanation
- ZERO em dashes (—) in output. This is non-negotiable.
- ZERO markdown bold (**word**) in output. Do not wrap any text in asterisks."""


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
