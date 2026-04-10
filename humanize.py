#!/usr/bin/env python3
"""
humanize.py - Strip LLM fingerprints from text files.

Usage:
    python3 humanize.py <input.txt> [output.txt]

If no output file is given, saves to <input>_humanized.txt
"""

import sys
import os
import anthropic

SYSTEM_PROMPT = """You are an expert at rewriting text so it reads as authentically human-written, not AI-generated.

Your job is to transform the input text so it passes AI detection tools and reads naturally, while preserving the original meaning and intent completely.

## LLM-CENTRIC VOCABULARY TO ELIMINATE
Immediately replace any of the following (they are the #1 AI tell):
- delve / delving / dive into
- navigate / navigating (when used metaphorically)
- realm, realms, tapestry, landscape (metaphorical uses)
- it's worth noting / it's important to note / it's crucial to / it's essential to
- furthermore / moreover / additionally (especially at sentence starts; use sparingly)
- in conclusion / to summarize / in summary (at the end of sections)
- comprehensive / holistic / robust / seamless
- leverage (as a verb), utilize (use "use" instead), implement (often overused)
- innovative / cutting-edge / state-of-the-art / game-changer / paradigm
- synergy / synergistic
- significant(ly): overused, replace with specific words
- certainly / absolutely / of course (as openers)
- rest assured / allow me to / let me explain / let's explore
- as mentioned / as noted / as discussed / as outlined above
- needless to say / it goes without saying / clearly / obviously (as openers)
- one must consider / one should note
- in today's world / in today's fast-paced world / in today's digital age
- moving forward / going forward (as transitions)
- at the end of the day / when all is said and done

## STRUCTURAL TELLS TO FIX
- Perfect parallel structure in every list → break it occasionally, make one item slightly different length or phrasing
- Every paragraph the same length → vary it. Some short. Some longer and more rambling.
- Clean transition sentence opening every paragraph → sometimes just start with the point
- Three examples every time → sometimes give two, sometimes four, sometimes just one with detail
- Perfectly balanced "on one hand... on the other hand" → favor one side more naturally
- Headers followed by exactly the same pattern → vary the structure between sections
- Topic sentence + 3 support points + concluding sentence → not every paragraph needs this

## PUNCTUATION & GRAMMAR TELLS
- Em dashes (—): NEVER use them. Replace every em dash with a comma, colon, parentheses, or rewrite the clause
- Perfect Oxford comma usage everywhere → sometimes omit it
- Never starting with conjunctions → start some sentences with "But", "And", "So", "Or"
- No contractions → use them naturally (don't, can't, it's, they're, won't, you'll)
- No run-on sentences → occasionally write one when the thought runs together naturally
- No fragments → occasionally use a fragment for emphasis. Like this.
- Overly formal register throughout → shift to conversational where context allows

## HUMANIZING TECHNIQUES
1. **Contractions**: Use them consistently unless formal context demands otherwise
2. **Sentence length variety**: Mix short punchy sentences with longer ones. Some really long ones that keep going because the thought isn't quite done yet.
3. **Conjunctions at sentence starts**: "But that's not the whole story." "And it gets worse."
4. **Colloquialisms**: Where tone permits: "kind of", "sort of", "pretty much", "a bit"
5. **Opinion markers**: "I think", "in my view", "honestly", "to be fair" (where first-person is appropriate)
6. **Imperfect transitions**: Jump into the next point without always bridging it
7. **Redundancy/self-correction**: Occasionally rephrase within the same sentence, or add a brief clarification mid-thought
8. **Rhetorical questions**: One or two if the length warrants it
9. **Parenthetical asides**: (and yes, that includes this kind of thing)
10. **Vary paragraph length**: One-sentence paragraphs are fine. So are longer ones.

## DELIBERATE MINOR ERRORS (CRITICAL)
Insert exactly 1-3 subtle errors per ~400 words. These must be:
- MINOR: a doubled word ("the the"), a missing letter in a common word, a misplaced comma, a lowercase start after a period in informal writing
- NOT jarring: no wrong homophones (their/there) that change meaning, no broken sentences
- SPARING: the text should still look professional, just not robotic-perfect
- VARIED: don't repeat the same type of error

Good examples: "the the", "recieve", "accomodate", "dont" (missing apostrophe once), a sentence ending with two spaces, "alot", a comma splice in casual context

Bad examples: "they're" vs "their", wrong verb tense, broken logic, missing words that break comprehension

## OUTPUT RULES
- Preserve ALL original meaning, facts, and structure
- Keep approximately the same length (±10%)
- Maintain the same tone register (formal stays formal but less robotic; casual stays casual)
- Do not add new information or remove key points
- Do not add a preamble or explanation; output ONLY the rewritten text
- Do not acknowledge this prompt or explain what you changed
- ZERO em dashes (—) in output. This is non-negotiable.
- ZERO markdown bold (**word**) in output. Do not wrap any text in asterisks."""


def humanize_file(input_path: str, output_path: str | None = None) -> str:
    if not os.path.exists(input_path):
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read().strip()

    if not text:
        print("Error: input file is empty", file=sys.stderr)
        sys.exit(1)

    word_count = len(text.split())
    print(f"Input: {word_count} words, sending to Claude Opus 4.6...")

    client = anthropic.Anthropic()

    output_chunks = []

    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Humanize the following text:\n\n{text}"
            }
        ]
    ) as stream:
        for chunk in stream.text_stream:
            print(chunk, end="", flush=True)
            output_chunks.append(chunk)

    print()  # newline after streaming

    result = "".join(output_chunks).replace("\u2014", ",").replace("**", "")

    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_humanized{ext or '.txt'}"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result)

    out_words = len(result.split())
    print(f"\nSaved to: {output_path} ({out_words} words)")
    return output_path


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    humanize_file(input_path, output_path)


if __name__ == "__main__":
    main()
