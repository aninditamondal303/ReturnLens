import { describe, expect, it } from "vitest";
import { inr, inrCompact, monthEnd, monthLabel, pct, pts, signedPct } from "./format";

describe("currency formatting", () => {
  it("uses Indian digit grouping", () => {
    expect(inr(50949554)).toBe("₹5,09,49,554");
  });
  it("compacts to lakh and crore", () => {
    expect(inrCompact(50949554)).toBe("₹5.09 Cr");
    expect(inrCompact(3371911)).toBe("₹33.7 L");
    expect(inrCompact(-806)).toBe("−₹806");
  });
  it("renders missing values as a dash, never as zero", () => {
    expect(inr(null)).toBe("—");
    expect(pct(undefined)).toBe("—");
  });
});

describe("rates", () => {
  it("formats fractions as percentages and points", () => {
    expect(pct(0.1272)).toBe("12.7%");
    expect(pts(0.012)).toBe("+1.2 pts");
    expect(pts(-0.004)).toBe("−0.4 pts");
    expect(signedPct(-0.052)).toBe("−5.2%");
  });
});

describe("months", () => {
  it("labels and finds month ends (incl. leap years)", () => {
    expect(monthLabel("2026-07")).toBe("Jul 26");
    expect(monthLabel("2026-07", true)).toBe("Jul 2026");
    expect(monthEnd("2026-02")).toBe("2026-02-28");
    expect(monthEnd("2028-02")).toBe("2028-02-29");
    expect(monthEnd("2025-12")).toBe("2025-12-31");
  });
});
