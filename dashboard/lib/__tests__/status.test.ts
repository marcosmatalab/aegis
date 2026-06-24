import { describe, expect, it } from "vitest";

import { statusTone } from "../status";

describe("statusTone", () => {
  it("maps each status to its intended tone", () => {
    expect(statusTone("measured")).toBe("success");
    expect(statusTone("covered")).toBe("success");
    expect(statusTone("estimated")).toBe("warn");
    expect(statusTone("partial")).toBe("warn");
    expect(statusTone("synthetic")).toBe("muted");
    expect(statusTone("placeholder")).toBe("muted");
    expect(statusTone("not_covered")).toBe("muted");
    expect(statusTone("out_of_scope")).toBe("neutral");
  });

  it("treats unknown statuses as muted, never success", () => {
    expect(statusTone("wat")).toBe("muted");
    expect(statusTone("")).toBe("muted");
  });

  it("THE invariant: only 'measured' and 'covered' may be success", () => {
    const nonSuccess = [
      "estimated",
      "synthetic",
      "placeholder",
      "partial",
      "not_covered",
      "out_of_scope",
      "unknown",
      "MEASURED", // case-sensitive — a mislabeled status must not sneak success
    ];
    for (const s of nonSuccess) {
      expect(statusTone(s)).not.toBe("success");
    }
  });
});
