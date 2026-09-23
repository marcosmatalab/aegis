# Scope, caveats and known limitations

The README states what Aegis does. This page states where each of those claims stops, in one
place, so none of them has to be discovered by reading the code.

## Project status

- **Pre-alpha, a portfolio project.** Phases F0–F9 are complete and tested offline
  ([roadmap](roadmap.md)). It is not a product with customers or production traffic.
- **Not published to PyPI.** Releases are git tags with a GitHub release that carries the
  wheel, the sdist and the evidence reports; install one with
  `pipx install "git+https://github.com/marcosmatalab/aegis@v0.1.2"`. Why, and what it costs:
  [ci-gates.md › Releasing](ci-gates.md#releasing).
- **Persistence is JSON reports on disk** (`reports/`, gitignored). There is no database.

## Judge calibration (κ)

- **Cohen's κ 0.933 is directional, not a verdict on the judge.** N=30, a single annotator
  (the author), and a calibration set written in the same model family as the judge. The
  confidence interval is wide. Full detail and the confusion matrix: [evals.md](evals.md#judge-calibration-f5).
- **The eval gate runs the deterministic mock judge**, so it guards the eval *pipeline*
  (scoring, aggregation, dataset, wiring) against its baseline. Whether the real judge is good
  is the separate question the calibration answers.
- **Agent-as-a-Judge:** the `MockTrajectoryJudge` is an illustrative heuristic (literal
  pattern matching, fixed penalty weights); the real LLM-backed `agent` backend is a stub.

## Red-team and guardrails

- **19/29 is coverage against the project's own catalog, not a security score.** The catalog
  deliberately includes payloads the deterministic scanners are known to miss, and all 10 gaps
  are named in the report's `known_gaps`: leetspeak override, injection in the non-scanned
  `system` / `assistant` / `developer` roles, a French override (patterns cover English and
  Spanish only), a base64-wrapped override (nothing is decoded), zero-width-space splitting (no
  unicode normalisation), an obfuscated email, a glued-digit credit card, and sub-threshold
  toxicity. See [redteam.md](redteam.md).
- **Only categories the guardrails genuinely exercise are mapped** (LLM01, LLM02, LLM07).
  Tool misuse (ASI02), identity (ASI03), LLM05 and LLM03/04/08/09/10 are out of scope for a
  stateless text proxy. Non-English coverage beyond the shipped Spanish variants is a gap.
- **Guardrails are off by default** (`AEGIS_GUARDRAILS_ENABLED=false`) and are
  defense-in-depth, not a claim of total detection. The default scanners are regex/lexicon;
  Presidio is optional.

## CI gates

- **The guarantee is "no *silent* regression", not "no regression ever".**
  `--update-baseline` can re-baseline worse numbers, but the baseline is committed, so doing
  so is a visible diff that a reviewer must approve. Review is the final backstop.
  Full contract: [ci-gates.md](ci-gates.md).

## Providers, governance and dashboard

- **Anthropic is the only real provider implemented.** The `Provider` interface is ready for
  others; OpenAI and Gemini are interface seams, not adapters.
- **The governance report is partial technical evidence, not a compliance certificate.** It
  maps a small set of technical controls; most of each framework's clauses are out of scope.
  See [governance.md](governance.md).
- **The live dashboard is a static snapshot of a real run**, and says so on the page.
- **`mypy` runs in its default mode, not `--strict`**; the trade-off is recorded in
  `pyproject.toml`.

---

[← back to the README](../README.md)
