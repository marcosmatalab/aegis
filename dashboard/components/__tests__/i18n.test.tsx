import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import type { Locale } from "@/lib/i18n/dictionaries";
import { LocaleProvider } from "@/lib/i18n/LocaleProvider";
import type { EvidenceView, RedteamView } from "@/lib/types";
import { EvidencePanel } from "../EvidencePanel";
import { RedteamPanel } from "../RedteamPanel";

function renderAt(locale: Locale, ui: ReactNode) {
  return render(<LocaleProvider initialLocale={locale}>{ui}</LocaleProvider>);
}

const redteam: RedteamView = {
  suite: "redteam",
  created: 0,
  caseCount: 25,
  overallDetectionRate: 0.72,
  overallOracleMatchRate: 1,
  categories: [
    {
      category: "prompt_injection",
      owasp: "LLM01",
      total: 11,
      blocked: 7,
      redacted: 0,
      passed: 4,
      detectionRate: 0.636,
      oracleMatchRate: 1,
    },
  ],
  knownGaps: [],
};

const evidence: EvidenceView = {
  generated: 0,
  suite: "golden",
  disclaimer: "PARTIAL TECHNICAL EVIDENCE",
  summaryCounts: { covered: 1, partial: 0, not_covered: 0, out_of_scope: 1 },
  inputsPresent: {},
  controls: [
    {
      framework: "ISO/IEC 42001:2023",
      controlId: "A.2",
      controlTitle: "x",
      status: "out_of_scope",
      artifactSource: "—",
      derivedValue: "Out of scope",
      caveat: "",
      verifiedVia: "",
    },
  ],
};

describe("panel i18n", () => {
  it("renders the English label in en", () => {
    renderAt("en", <RedteamPanel view={redteam} />);
    expect(screen.getByText("Got through")).toBeInTheDocument();
    expect(screen.queryByText("Se colaron")).not.toBeInTheDocument();
  });

  it("renders the Spanish label in es", () => {
    renderAt("es", <RedteamPanel view={redteam} />);
    expect(screen.getByText("Se colaron")).toBeInTheDocument();
    expect(screen.queryByText("Got through")).not.toBeInTheDocument();
  });

  it("NEVER translates a verbatim report status enum, even in es", () => {
    renderAt("es", <EvidencePanel view={evidence} />);
    // the status enum is shown verbatim (untranslated) and is never success-coloured
    const badge = screen.getByText("out_of_scope");
    expect(badge).toBeInTheDocument();
    expect(badge.getAttribute("data-tone")).not.toBe("success");
    // the surrounding caveat IS translated to Spanish (prose, not data)
    expect(screen.getByText(/porcentaje de cobertura/)).toBeInTheDocument();
  });
});
