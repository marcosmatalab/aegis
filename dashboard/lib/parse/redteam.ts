import type { RedteamCategoryView, RedteamGapView, RedteamView } from "../types";
import { asArray, asNumber, asObject, asString } from "./raw";

/** Parse a raw red-team report into a RedteamView, or null if not an object. */
export function parseRedteam(raw: unknown): RedteamView | null {
  const o = asObject(raw);
  if (!o) return null;

  const catsRaw = asObject(o.categories) ?? {};
  const categories: RedteamCategoryView[] = Object.entries(catsRaw)
    .map(([category, v]) => {
      const c = asObject(v) ?? {};
      return {
        category,
        owasp: asString(c.owasp),
        total: asNumber(c.total),
        blocked: asNumber(c.blocked),
        redacted: asNumber(c.redacted),
        passed: asNumber(c.passed),
        detectionRate: asNumber(c.detection_rate),
        oracleMatchRate: asNumber(c.oracle_match_rate),
      };
    })
    .sort((a, b) => a.category.localeCompare(b.category));

  // known_gaps are SURFACED verbatim — they are the red-team honesty signal.
  const knownGaps: RedteamGapView[] = asArray(o.known_gaps)
    .map((g) => asObject(g))
    .filter((g): g is Record<string, unknown> => g !== null)
    .map((g) => ({
      id: asString(g.id) ?? "?",
      category: asString(g.category),
      owasp: asString(g.owasp),
      gapReason: asString(g.gap_reason),
    }));

  const overall = asObject(o.overall) ?? {};
  return {
    suite: asString(o.suite),
    created: asNumber(o.created),
    caseCount: asNumber(o.case_count),
    overallDetectionRate: asNumber(overall.detection_rate),
    overallOracleMatchRate: asNumber(overall.oracle_match_rate),
    categories,
    knownGaps,
  };
}
