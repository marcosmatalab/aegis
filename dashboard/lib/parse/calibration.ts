import type { CalibrationView, ConfusionView, CriterionView, KappaSectionView } from "../types";
import { asNumber, asObject, asString } from "./raw";

const CRITERIA = ["relevancy", "faithfulness"];

function parseMatrix(raw: unknown): ConfusionView | null {
  const m = asObject(raw);
  if (!m) return null;
  return {
    orientation: asString(m.orientation),
    humanPassJudgePass: asNumber(m.human_pass_judge_pass),
    humanPassJudgeFail: asNumber(m.human_pass_judge_fail),
    humanFailJudgePass: asNumber(m.human_fail_judge_pass),
    humanFailJudgeFail: asNumber(m.human_fail_judge_fail),
  };
}

function parseSection(raw: unknown): KappaSectionView | null {
  const o = asObject(raw);
  if (!o) return null;
  // kappa stays null (undefined/degenerate) — the UI must show "undefined", never 0.
  return {
    kappa: asNumber(o.kappa),
    pO: asNumber(o.p_o),
    pE: asNumber(o.p_e),
    nValid: asNumber(o.n_valid),
    band: asString(o.band),
    matrix: parseMatrix(o.confusion_matrix),
  };
}

/** Parse a raw calibration report into a CalibrationView, or null if not an object. */
export function parseCalibration(raw: unknown): CalibrationView | null {
  const o = asObject(raw);
  if (!o) return null;

  const pcRaw = asObject(o.per_criterion) ?? {};
  const perCriterion: CriterionView[] = [];
  for (const criterion of CRITERIA) {
    const section = parseSection(pcRaw[criterion]);
    if (section) perCriterion.push({ criterion, section });
  }

  const judge = asString(o.judge);
  return {
    judge,
    judgeIsMock: judge === "mock",
    threshold: asNumber(o.threshold),
    nCases: asNumber(o.n_cases),
    nParseFailed: asNumber(o.n_parse_failed),
    global: parseSection(o.global),
    perCriterion,
  };
}
