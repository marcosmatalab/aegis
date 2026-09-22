"""Shared foundation every other Aegis layer is allowed to depend on.

``core`` holds the two things that are genuinely common — the OpenAI-compatible
wire ``schemas`` and the runtime ``config`` — and nothing else. It imports no
other Aegis package, which is what makes it a base layer rather than a grab bag.

WHY IT EXISTS. These modules used to live in ``aegis.gateway``, so every layer
that needed a ``ChatCompletionRequest`` or a ``Settings`` had to import the HTTP
layer to get one. ``guardrails`` did exactly that, while ``gateway.proxy``
imports ``guardrails`` — a genuine ``gateway <-> guardrails`` import cycle, with
no test or lint step that would have noticed. Moving the shared types down into
``core`` breaks the cycle at its cause instead of tolerating it, and
``.importlinter`` now pins the resulting layering in CI.
"""
