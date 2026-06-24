import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AbsentPanel } from "../AbsentPanel";

describe("AbsentPanel", () => {
  it("reads as an explicit absence (never a zero/blank that looks fine)", () => {
    const { container } = render(
      <AbsentPanel
        title="Calibration (κ)"
        reason="no calibration report at reports/calibration.json"
        hint="run: aegis calibrate --judge geval"
      />,
    );
    expect(screen.getByText(/Not available/)).toBeInTheDocument();
    expect(screen.getByText(/no calibration report/)).toBeInTheDocument();
    expect(screen.getByText(/aegis calibrate --judge geval/)).toBeInTheDocument();
    expect(container.querySelector("[data-absent='true']")).not.toBeNull();
  });

  it("omits the hint line when none is given", () => {
    render(<AbsentPanel title="Red-team" reason="no red-team report" />);
    expect(screen.queryByText(/Hint:/)).toBeNull();
  });
});
