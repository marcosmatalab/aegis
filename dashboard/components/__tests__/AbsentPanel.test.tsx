import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AbsentPanel } from "../AbsentPanel";

describe("AbsentPanel", () => {
  it("reads as an explicit absence (never a zero/blank that looks fine)", () => {
    const { container } = render(
      <AbsentPanel
        titleKey="kappa.title"
        reasonKey="absent.calibrationReason"
        command="aegis calibrate --judge geval"
      />,
    );
    // default-EN context (no provider): renders the English strings
    expect(screen.getByText(/Not available/)).toBeInTheDocument();
    expect(screen.getByText(/no calibration.json/)).toBeInTheDocument();
    // the CLI command is rendered VERBATIM, never translated
    expect(screen.getByText(/aegis calibrate --judge geval/)).toBeInTheDocument();
    expect(container.querySelector("[data-absent='true']")).not.toBeNull();
  });

  it("omits the command line when none is given", () => {
    render(<AbsentPanel titleKey="redteam.title" reasonKey="absent.redteamReason" />);
    expect(screen.queryByText(/run to produce it/)).toBeNull();
  });
});
