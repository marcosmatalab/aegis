# Security policy

## Reporting a vulnerability

Please report security issues **privately** through GitHub's
[private vulnerability reporting](https://github.com/marcosmatalab/aegis/security/advisories/new)
rather than opening a public issue.

Expect an acknowledgement within a few days. This is a portfolio project maintained by one
person, so there is no paid support and no bounty — but a real report will get a real answer
and a credited fix.

## What this project is, and is not

Aegis is a **portfolio project, pre-alpha**. Do not treat it as a hardened security product.
Being straight about the boundary matters more here than anywhere else, because the project's
subject is guardrails:

- **The guardrails are defence-in-depth, not total detection.** Coverage is measured against a
  committed attack catalog and published per OWASP category. The current figure is
  **18/25 detected**, and the **7 attacks that get through are named in the report**, not
  rounded away. Reproduce it with `aegis redteam run`.
- **Known gaps are documented, not hidden.** Leetspeak substitution, system/developer/assistant
  role text not being scanned, obfuscated emails, a card number glued into a longer digit run,
  and sub-threshold toxicity. They are in the catalog as `*-gap-*` cases precisely so a
  regression in them is visible.
- **Coverage against a catalog is not a security score.** A 0.720 detection rate means the
  catalog is 72% detected. It says nothing about attacks the catalog does not contain.

## Scope

In scope: the gateway (`src/aegis/gateway/`), the guardrail pipeline
(`src/aegis/guardrails/`), and anything that could leak a key, bypass a guardrail silently, or
make a gate report a pass it should not.

Out of scope: the known gaps listed above (already public), the deliberately permissive
keyless mock provider, and the dashboard's rendering of local report files.

## Secrets

The gateway is **keyless by default** and runs entirely on a deterministic mock. No secret is
required to run, test, lint or gate this project. Real provider keys are read from the
environment or a local `.env`, which is gitignored — never from committed configuration.
