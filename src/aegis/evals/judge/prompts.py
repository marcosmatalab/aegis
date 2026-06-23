"""Prompt templates for the real (G-Eval-INSPIRED) LLM-as-judge.

This is G-Eval-INSPIRED, not canonical: it uses light Chain-of-Thought (the judge
justifies before scoring, which curbs the systematic optimism of naive
LLM-as-judge) but reads the score DIRECTLY from the reply — it does NOT do
canonical G-Eval's logprob-weighted scoring, because the Anthropic API does not
expose per-token logprobs. The reasoning is BOUNDED and kept INSIDE a compact
single-line JSON object so it cannot grow unbounded and truncate the score before
the token budget is reached (a truncation would parse-fail to a neutral score).
"""

G_EVAL_SYSTEM = (
    "You are a rigorous, impartial evaluator. You reason carefully before scoring "
    "and never inflate scores."
)

# Note: the literal JSON braces are doubled for str.format(). Reasoning lives
# INSIDE the JSON (bounded to one or two sentences) and the model is told to emit
# ONLY the JSON, so there is no unbounded free-text reasoning before the score.
G_EVAL_TEMPLATE = (
    "Score how well the OUTPUT meets the CRITERION, from 0 (fails) to 1 (fully "
    "meets). Think step by step but be concise. Output ONLY a single-line JSON "
    "object and nothing else, with the reasoning BEFORE the score: "
    '{{"reasoning": "<one or two sentences>", "score": <number between 0 and 1>}}.\n\n'
    "CRITERION: {criteria}\n"
    "--- OUTPUT ---\n{output}\n"
    "--- REFERENCE ---\n{reference}\n"
    "--- CONTEXT ---\n{context}\n"
)
