// Display helpers. A null (absent) value ALWAYS renders as an em-dash, never 0 —
// so missing data reads as missing, not as a real measurement of zero.

export const ABSENT = "—";

export function fmtNum(x: number | null, digits = 3): string {
  return x === null ? ABSENT : x.toFixed(digits);
}

export function fmtPct(x: number | null, digits = 1): string {
  return x === null ? ABSENT : `${(x * 100).toFixed(digits)}%`;
}

export function fmtInt(x: number | null): string {
  return x === null ? ABSENT : String(x);
}

/** Format a unix-seconds timestamp as a UTC string (deterministic given the input). */
export function fmtUnixUtc(x: number | null): string {
  if (x === null) return ABSENT;
  return new Date(x * 1000).toISOString().replace("T", " ").replace(".000Z", " UTC");
}
