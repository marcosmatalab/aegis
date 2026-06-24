// Status -> visual tone. THE honesty invariant of the whole dashboard: only the
// genuinely-good statuses ("measured", "covered") may render as success (green).
// Every other status — estimated/synthetic/placeholder (CLEAR), partial/not_covered/
// out_of_scope (evidence), or anything unrecognized — is visibly NON-success, so the
// UI can never look rosier than the report. The badge LABEL is always the verbatim
// status string (see StatusBadge); this only controls colour.

export type Tone = "success" | "warn" | "muted" | "neutral";

const TONES: Record<string, Tone> = {
  // genuinely measured/satisfied
  measured: "success",
  covered: "success",
  // real but qualified — must read as a caveat, never success
  estimated: "warn",
  partial: "warn",
  // not a real measurement / not satisfied
  synthetic: "muted",
  placeholder: "muted",
  not_covered: "muted",
  // structurally not applicable
  out_of_scope: "neutral",
};

/** Map a status to a tone. Unknown/unmapped statuses are "muted" — NEVER success. */
export function statusTone(status: string): Tone {
  return TONES[status] ?? "muted";
}
