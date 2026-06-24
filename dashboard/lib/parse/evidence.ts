import type { EvidenceControlView, EvidenceView } from "../types";
import { asArray, asBoolean, asNumber, asObject, asString } from "./raw";

/** Parse a raw F8 evidence sidecar into an EvidenceView, or null if not an object. */
export function parseEvidence(raw: unknown): EvidenceView | null {
  const o = asObject(raw);
  if (!o) return null;

  const sc = asObject(o.summary_counts) ?? {};
  const ipRaw = asObject(o.inputs_present) ?? {};
  const inputsPresent: Record<string, boolean> = {};
  for (const [k, v] of Object.entries(ipRaw)) inputsPresent[k] = asBoolean(v);

  const controls: EvidenceControlView[] = asArray(o.controls)
    .map((c) => asObject(c))
    .filter((c): c is Record<string, unknown> => c !== null)
    .map((c) => ({
      framework: asString(c.framework) ?? "?",
      controlId: asString(c.control_id) ?? "?",
      controlTitle: asString(c.control_title) ?? "?",
      status: asString(c.status) ?? "unknown", // verbatim
      artifactSource: asString(c.artifact_source),
      derivedValue: asString(c.derived_value),
      caveat: asString(c.caveat),
      verifiedVia: asString(c.verified_via),
    }));

  return {
    generated: asNumber(o.generated),
    suite: asString(o.suite),
    disclaimer: asString(o.disclaimer),
    summaryCounts: {
      covered: asNumber(sc.covered) ?? 0,
      partial: asNumber(sc.partial) ?? 0,
      not_covered: asNumber(sc.not_covered) ?? 0,
      out_of_scope: asNumber(sc.out_of_scope) ?? 0,
    },
    inputsPresent,
    controls,
  };
}
