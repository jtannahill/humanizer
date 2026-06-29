"""Behavioral test for the RoBERTa classifier backend.

Unlike the zero-shot backends (gpt2 / binoculars / fast_detectgpt), this one
is a supervised classifier emitting a calibrated P(AI), so the meaningful
correctness property is *separation*: the AI sample must read as more AI-like
than the human sample. This also catches the #1 wiring risk — flipping the
human/AI class index — which a frozen-number parity test would silently pass.
"""

import roberta_scorer


def test_dict_shape(ai_text):
    result = roberta_scorer.score(ai_text)
    assert "roberta" in result        # P(AI), 0-1
    assert "burstiness" in result
    assert "human_score" in result
    assert 0.0 <= result["roberta"] <= 1.0
    assert 0.0 <= result["human_score"] <= 1.0


def test_separates_ai_from_human(ai_text, human_text):
    ai = roberta_scorer.score(ai_text)
    human = roberta_scorer.score(human_text)

    # Classifier: AI sample carries higher P(AI) than the human sample.
    assert ai["roberta"] > human["roberta"], (
        f"no separation: P(AI) ai={ai['roberta']:.3f} human={human['roberta']:.3f}"
    )
    # Oracle: AI sample is judged less human than the human sample.
    assert ai["human_score"] < human["human_score"], (
        f"human_score not ordered: ai={ai['human_score']:.3f} "
        f"human={human['human_score']:.3f}"
    )


def test_worst_sentences_present_when_requested(ai_text):
    result = roberta_scorer.score(ai_text, with_sentences=True)
    assert "worst_sentences" in result
    assert "sentences" in result
    assert len(result["worst_sentences"]) >= 1
