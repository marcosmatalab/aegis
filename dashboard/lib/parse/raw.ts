// Defensive coercion helpers for parsing the Python-written report JSON.
//
// The dashboard parses JSON produced by a SEPARATE codebase (the Python writers).
// Schema drift, partial/interrupted writes, or a wrong file must degrade to absent
// (null) — NEVER crash and NEVER fabricate a value. Every parser is built only from
// these helpers, so a missing/null/wrong-typed field becomes null, not a guess.

export function asObject(x: unknown): Record<string, unknown> | null {
  return x !== null && typeof x === "object" && !Array.isArray(x)
    ? (x as Record<string, unknown>)
    : null;
}

export function asNumber(x: unknown): number | null {
  return typeof x === "number" && Number.isFinite(x) ? x : null;
}

export function asString(x: unknown): string | null {
  return typeof x === "string" ? x : null;
}

/** Strict boolean: only literal `true` is true; anything else (incl. truthy) is false. */
export function asBoolean(x: unknown): boolean {
  return x === true;
}

export function asArray(x: unknown): unknown[] {
  return Array.isArray(x) ? x : [];
}
