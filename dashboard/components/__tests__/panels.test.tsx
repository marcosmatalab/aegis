import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ClearDimView, EvalView, EvidenceView } from "@/lib/types";
import { ClearPanel } from "../ClearPanel";
import { EvalScorecard } from "../EvalScorecard";
import { EvidencePanel } from "../EvidencePanel";

describe("ClearPanel", () => {
  it("renders a placeholder dim verbatim and never as success", () => {
    const dims: ClearDimView[] = [
      {
        name: "cost",
        status: "placeholder",
        applicable: false,
        score: null,
        value: null,
        unit: "usd",
        basis: "no telemetry",
      },
    ];
    render(<ClearPanel dims={dims} />);
    expect(screen.getByText("placeholder").getAttribute("data-tone")).not.toBe("success");
  });
});

describe("EvalScorecard", () => {
  it("surfaces the mock-judge caveat", () => {
    const view: EvalView = {
      suite: "golden",
      judge: "mock",
      judgeIsMock: true,
      caseCount: 1,
      created: 0,
      overallScore: 0.5,
      levels: [],
      clear: [],
      trajectory: [],
    };
    render(<EvalScorecard view={view} />);
    expect(screen.getByText(/wiring smoke test/)).toBeInTheDocument();
  });
});

describe("EvidencePanel", () => {
  it("renders out_of_scope verbatim + the not-a-coverage caveat", () => {
    const view: EvidenceView = {
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
    render(<EvidencePanel view={view} />);
    expect(screen.getByText("out_of_scope").getAttribute("data-tone")).not.toBe("success");
    expect(screen.getByText(/NOT a coverage percentage/)).toBeInTheDocument();
  });
});
