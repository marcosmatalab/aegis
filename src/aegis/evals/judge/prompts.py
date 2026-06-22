"""Prompt templates for the real (G-Eval) LLM-as-judge.

G-Eval = Chain-of-Thought rubric judging: the judge reasons step by step BEFORE
emitting a score, which reduces the systematic optimism of naive LLM-as-judge.
"""

G_EVAL_SYSTEM = (
    "You are a rigorous, impartial evaluator. You reason carefully before scoring "
    "and never inflate scores."
)

# Note: the literal JSON braces are doubled for str.format().
G_EVAL_TEMPLATE = (
    "Evaluate the OUTPUT against the CRITERION. First reason step by step about how "
    "well the output meets the criterion, then return ONLY a JSON object on the last "
    'line: {{"reasoning": "<concise reasoning>", "score": <number between 0 and 1>}}.\n\n'
    "CRITERION: {criteria}\n"
    "--- OUTPUT ---\n{output}\n"
    "--- REFERENCE ---\n{reference}\n"
    "--- CONTEXT ---\n{context}\n"
)
