// Typed view-models the dashboard renders. Every numeric field is `number | null`
// (null => render an explicit em-dash / "absent", never 0). Status strings are kept
// VERBATIM (even if unknown) so the UI can never launder a non-success status.

// --- eval report ---------------------------------------------------------- //
export type ClearStatus = "measured" | "estimated" | "synthetic" | "placeholder";

export interface ClearDimView {
  name: string;
  status: string; // verbatim — usually ClearStatus, kept as-is even if unrecognized
  applicable: boolean;
  score: number | null;
  value: number | null;
  unit: string | null;
  basis: string | null;
}

export interface LevelView {
  level: string; // "L1" | "L2" | "L3"
  meanScore: number | null;
  passed: number | null;
  scored: number | null;
}

export interface TrajectoryMetricView {
  metric: string;
  meanScore: number | null;
  scored: number | null;
}

export interface EvalView {
  suite: string | null;
  judge: string | null;
  judgeIsMock: boolean; // judge === "mock" => results are a wiring smoke test, not real
  caseCount: number | null;
  created: number | null;
  overallScore: number | null;
  levels: LevelView[];
  clear: ClearDimView[];
  trajectory: TrajectoryMetricView[];
}

// --- red-team report ------------------------------------------------------ //
export interface RedteamCategoryView {
  category: string;
  owasp: string | null;
  total: number | null;
  blocked: number | null;
  redacted: number | null;
  passed: number | null;
  detectionRate: number | null;
  oracleMatchRate: number | null;
}

export interface RedteamGapView {
  id: string;
  category: string | null;
  owasp: string | null;
  gapReason: string | null;
}

export interface RedteamView {
  suite: string | null;
  created: number | null;
  caseCount: number | null;
  overallDetectionRate: number | null;
  overallOracleMatchRate: number | null;
  categories: RedteamCategoryView[];
  knownGaps: RedteamGapView[];
}

// --- calibration report --------------------------------------------------- //
export interface ConfusionView {
  orientation: string | null;
  humanPassJudgePass: number | null;
  humanPassJudgeFail: number | null;
  humanFailJudgePass: number | null;
  humanFailJudgeFail: number | null;
}

export interface KappaSectionView {
  kappa: number | null; // null => undefined (degenerate table) — never shown as a number
  pO: number | null;
  pE: number | null;
  nValid: number | null;
  band: string | null; // "undefined" when kappa is null
  matrix: ConfusionView | null;
}

export interface CriterionView {
  criterion: string;
  section: KappaSectionView;
}

export interface CalibrationView {
  judge: string | null;
  judgeIsMock: boolean;
  threshold: number | null;
  nCases: number | null;
  nParseFailed: number | null;
  global: KappaSectionView | null;
  perCriterion: CriterionView[];
}

// --- F8 evidence report --------------------------------------------------- //
export type EvidenceStatus = "covered" | "partial" | "not_covered" | "out_of_scope";

export interface EvidenceControlView {
  framework: string;
  controlId: string;
  controlTitle: string;
  status: string; // verbatim — usually EvidenceStatus
  artifactSource: string | null;
  derivedValue: string | null;
  caveat: string | null;
  verifiedVia: string | null;
}

export interface EvidenceView {
  generated: number | null;
  suite: string | null;
  disclaimer: string | null;
  summaryCounts: { covered: number; partial: number; not_covered: number; out_of_scope: number };
  inputsPresent: Record<string, boolean>;
  controls: EvidenceControlView[];
}
