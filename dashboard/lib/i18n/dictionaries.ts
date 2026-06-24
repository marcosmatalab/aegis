// UI string dictionaries for the dashboard. `en` is the SINGLE source of truth; `es`
// is typed `Dict` so tsc fails if its key set diverges (a runtime test double-checks).
//
// HONESTY INVARIANT: dictionaries hold ONLY labels / titles / descriptions / prose.
// The verbatim report ENUMS — measured/estimated/synthetic/placeholder and
// covered/partial/not_covered/out_of_scope — and every report DATUM (numbers, dates,
// filenames, disclaimers, derived values, κ bands, category names, gap reasons) are
// rendered raw by the components and never appear here, so they can never be translated.

export const en = {
  page: {
    title: "🛡️ Aegis dashboard",
    subtitlePre: "Read-only view of the real reports in ",
    subtitlePost:
      ". Statuses and caveats are shown verbatim; absent reports are marked, never faked.",
  },
  toggle: {
    aria: "Language",
  },
  eval: {
    title: "Evaluation (L1/L2/L3)",
    absentTitle: "Evaluation (L1/L2/L3) + CLEAR",
    subtitle: "suite={suite} · judge={judge} · {n} cases · {date}",
    mockCaveat:
      "judge=mock — a deterministic wiring smoke test (L2 by the heuristic judge), not a real-judge evaluation",
    colLevel: "Level",
    colMean: "Mean",
    colPassed: "Passed",
    overallLabel: "overall",
    trajectoryLabel: "trajectory",
  },
  clear: {
    title: "CLEAR",
    caveat:
      "Cost/Latency are only real with OpenTelemetry telemetry (F1.x); on the offline mock suite they stay placeholder/synthetic — shown verbatim, never as a measured number.",
    colDimension: "Dimension",
    colStatus: "Status",
    colValue: "Value",
    colBasis: "Basis",
    na: "n/a",
  },
  redteam: {
    title: "Red-team (OWASP)",
    subtitle: "{n} attacks · overall detection {pct}",
    caveat:
      "Detection rate is DIRECTIONAL coverage-against-the-catalog, not a pass/fail compliance number. 'Got through' counts attacks that BYPASSED the guardrails (a miss — higher is worse), not test passes. The named gaps below get through by design and are disclosed, not hidden.",
    colCategory: "Category",
    colOwasp: "OWASP",
    colDetection: "Detection",
    gotThrough: "Got through",
    namedGaps: "Named gaps ({count}) — get through by design",
    noneInRun: "none in this run",
  },
  kappa: {
    title: "Judge calibration (Cohen's κ)",
    subtitle: "judge={judge} · n={n} · parse-failed={pf}",
    caveatDirectional:
      "Cohen's κ is DIRECTIONAL — agreement with one annotator's rubric, not ground truth.",
    caveatSmallN: "Small N — read κ with p_o and the confusion matrix, never alone.",
    caveatDegenerate:
      "Landis-Koch bands are arbitrary conventions; a degenerate table yields an undefined κ (shown as 'undefined', never 0).",
    mockCaveat:
      "judge=mock — a wiring smoke test (κ of the heuristic mock vs the labels), not a real-judge calibration",
    colScope: "Scope",
    colKappa: "κ (band)",
    colPo: "p_o",
    colN: "n",
    globalRow: "global",
    matrixTitle: "Global confusion matrix",
    matrixOrientationDefault: "rows=human, cols=judge; positive='pass'",
    cellHpJp: "human pass / judge pass",
    cellHpJf: "human pass / judge fail",
    cellHfJp: "human fail / judge pass",
    cellHfJf: "human fail / judge fail",
  },
  evidence: {
    title: "Governance evidence (F8)",
    partialCoverageNote:
      "Counts are over the small set of mapped technical controls — NOT a coverage percentage; most framework clauses are out of scope.",
    colControl: "Control",
    colStatus: "Status",
    colEvidence: "Evidence",
  },
  absent: {
    notAvailable: "Not available",
    runToProduce: "run to produce it:",
    evalReason: "no eval-*.json in the reports directory",
    redteamReason: "no redteam-*.json in the reports directory",
    calibrationReason: "no calibration.json in the reports directory",
    evidenceReason: "no evidence-*.json in the reports directory",
  },
  runs: {
    title: "Runs & reports",
    present: "present",
    absent: "absent",
    kindEval: "eval",
    kindRedteam: "red-team",
    kindCalibration: "calibration",
    kindEvidence: "evidence",
    noEvalRuns: "No eval runs in this directory.",
    overall: "overall",
  },
  trends: {
    title: "Trends (across eval runs)",
    noRuns: "No eval runs yet.",
    needTwoRuns:
      "Single eval run — no trend yet (a trend line is never drawn for fewer than two real runs).",
    runsSubtitle: "{n} runs",
  },
};

export type Dict = typeof en;
export type Locale = "en" | "es";

// Dot-path union of every leaf key, so t() is typed and a typo is a compile error.
type Paths<T> = T extends string
  ? never
  : { [K in keyof T & string]: T[K] extends string ? K : `${K}.${Paths<T[K]>}` }[keyof T & string];
export type TKey = Paths<Dict>;

// `es` MUST mirror `en` exactly (compile-time via Dict; runtime via dictionaries.test).
// Professional Castilian; technical tokens (suite/judge/OWASP/p_o/pass/fail/parse-failed)
// and acronyms (CLEAR, κ) are kept as-is on purpose.
export const es: Dict = {
  page: {
    title: "🛡️ Panel de Aegis",
    subtitlePre: "Vista de solo lectura de los reportes reales en ",
    subtitlePost:
      ". Los estados y las advertencias se muestran literalmente; los reportes ausentes se marcan, nunca se falsean.",
  },
  toggle: {
    aria: "Idioma",
  },
  eval: {
    title: "Evaluación (L1/L2/L3)",
    absentTitle: "Evaluación (L1/L2/L3) + CLEAR",
    subtitle: "suite={suite} · judge={judge} · {n} casos · {date}",
    mockCaveat:
      "judge=mock — una prueba de humo determinista del cableado (L2 con el juez heurístico), no una evaluación con juez real",
    colLevel: "Nivel",
    colMean: "Media",
    colPassed: "Superados",
    overallLabel: "global",
    trajectoryLabel: "trayectoria",
  },
  clear: {
    title: "CLEAR",
    caveat:
      "Coste/Latencia solo son reales con telemetría de OpenTelemetry (F1.x); en la suite mock offline permanecen como placeholder/synthetic — mostrados literalmente, nunca como un número medido.",
    colDimension: "Dimensión",
    colStatus: "Estado",
    colValue: "Valor",
    colBasis: "Base",
    na: "n/d",
  },
  redteam: {
    title: "Red-team (OWASP)",
    subtitle: "{n} ataques · detección global {pct}",
    caveat:
      "La tasa de detección es cobertura DIRECCIONAL frente al catálogo, no un número de cumplimiento aprobado/fallido. 'Se colaron' cuenta los ataques que ESQUIVARON los guardrails (un fallo — más alto es peor), no pruebas superadas. Las brechas nombradas de abajo se cuelan por diseño y se divulgan, no se ocultan.",
    colCategory: "Categoría",
    colOwasp: "OWASP",
    colDetection: "Detección",
    gotThrough: "Se colaron",
    namedGaps: "Brechas conocidas ({count}) — se cuelan por diseño",
    noneInRun: "ninguna en esta corrida",
  },
  kappa: {
    title: "Calibración del juez (κ de Cohen)",
    subtitle: "judge={judge} · n={n} · parse-failed={pf}",
    caveatDirectional:
      "La κ de Cohen es DIRECCIONAL — concordancia con la rúbrica de un anotador, no la verdad absoluta.",
    caveatSmallN: "N pequeña — lee κ junto a p_o y la matriz de confusión, nunca a solas.",
    caveatDegenerate:
      "Las bandas de Landis-Koch son convenciones arbitrarias; una tabla degenerada da una κ indefinida (mostrada como 'undefined', nunca 0).",
    mockCaveat:
      "judge=mock — una prueba de humo del cableado (κ del mock heurístico frente a las etiquetas), no una calibración con juez real",
    colScope: "Ámbito",
    colKappa: "κ (banda)",
    colPo: "p_o",
    colN: "n",
    globalRow: "global",
    matrixTitle: "Matriz de confusión global",
    matrixOrientationDefault: "filas=humano, cols=juez; positivo='pass'",
    cellHpJp: "humano pass / juez pass",
    cellHpJf: "humano pass / juez fail",
    cellHfJp: "humano fail / juez pass",
    cellHfJf: "humano fail / juez fail",
  },
  evidence: {
    title: "Evidencia de gobernanza (F8)",
    partialCoverageNote:
      "Los recuentos son sobre el pequeño conjunto de controles técnicos mapeados — NO un porcentaje de cobertura; la mayoría de las cláusulas de los marcos quedan fuera de alcance.",
    colControl: "Control",
    colStatus: "Estado",
    colEvidence: "Evidencia",
  },
  absent: {
    notAvailable: "No disponible",
    runToProduce: "ejecútalo para generarlo:",
    evalReason: "no hay eval-*.json en el directorio de reportes",
    redteamReason: "no hay redteam-*.json en el directorio de reportes",
    calibrationReason: "no hay calibration.json en el directorio de reportes",
    evidenceReason: "no hay evidence-*.json en el directorio de reportes",
  },
  runs: {
    title: "Corridas y reportes",
    present: "presente",
    absent: "ausente",
    kindEval: "eval",
    kindRedteam: "red-team",
    kindCalibration: "calibración",
    kindEvidence: "evidencia",
    noEvalRuns: "No hay corridas de eval en este directorio.",
    overall: "global",
  },
  trends: {
    title: "Tendencias (entre corridas de eval)",
    noRuns: "Aún no hay corridas de eval.",
    needTwoRuns:
      "Una sola corrida de eval — aún no hay tendencia (nunca se dibuja una línea de tendencia con menos de dos corridas reales).",
    runsSubtitle: "{n} corridas",
  },
};

export const dictionaries: Record<Locale, Dict> = { en, es };

/** Resolve a dot-path key against a dict; undefined if any segment is missing. */
export function lookup(dict: Dict, key: string): string | undefined {
  const parts = key.split(".");
  let node: unknown = dict;
  for (const p of parts) {
    if (node === null || typeof node !== "object") return undefined;
    node = (node as Record<string, unknown>)[p];
  }
  return typeof node === "string" ? node : undefined;
}

function interpolate(raw: string, vars: Record<string, string | number>): string {
  return raw.replace(/\{(\w+)\}/g, (_m, k: string) => (k in vars ? String(vars[k]) : `{${k}}`));
}

/**
 * Translate `key` against `primary`, falling back to `fallback` (English) and finally
 * to the key itself — so a missing string degrades visibly, never silently to blank.
 */
export function translate(
  primary: Dict,
  fallback: Dict,
  key: string,
  vars?: Record<string, string | number>,
): string {
  const raw = lookup(primary, key) ?? lookup(fallback, key) ?? key;
  return vars ? interpolate(raw, vars) : raw;
}
