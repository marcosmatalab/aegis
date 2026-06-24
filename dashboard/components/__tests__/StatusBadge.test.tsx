import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusBadge } from "../StatusBadge";

describe("StatusBadge", () => {
  it("renders the status string VERBATIM (never relabeled)", () => {
    render(<StatusBadge status="placeholder" />);
    expect(screen.getByText("placeholder")).toBeInTheDocument();
  });

  it("gives measured/covered the success tone", () => {
    const { rerender } = render(<StatusBadge status="measured" />);
    expect(screen.getByText("measured").getAttribute("data-tone")).toBe("success");
    rerender(<StatusBadge status="covered" />);
    expect(screen.getByText("covered").getAttribute("data-tone")).toBe("success");
  });

  it("never gives a non-success status the success tone", () => {
    for (const status of ["estimated", "synthetic", "placeholder", "partial", "not_covered"]) {
      const { unmount } = render(<StatusBadge status={status} />);
      expect(screen.getByText(status).getAttribute("data-tone")).not.toBe("success");
      unmount();
    }
  });
});
