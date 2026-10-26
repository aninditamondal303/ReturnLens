import { describe, expect, it } from "vitest";
import { buildQuery, scenarioQuery } from "./api";

describe("buildQuery", () => {
  it("drops empty values and encodes the rest", () => {
    expect(buildQuery({ category: "Women's Fashion", region: "", channel: undefined, page: 2 })).toBe(
      "?category=Women%27s+Fashion&page=2",
    );
    expect(buildQuery({})).toBe("");
  });
});

describe("scenarioQuery", () => {
  it("serialises category overrides as percentages", () => {
    const q = scenarioQuery({
      return_reduction: 0.1,
      logistics_reduction: 0.05,
      write_off_reduction: 0.2,
      retained_sale_share: 0.65,
      prevention_spend: 150000.4,
      category_overrides: { Footwear: 0.2, "Home & Kitchen": 0.15 },
    });
    expect(q.category_overrides).toBe("Footwear:20,Home & Kitchen:15");
    expect(q.prevention_spend).toBe(150000);
  });
  it("omits overrides when none are set", () => {
    const q = scenarioQuery({
      return_reduction: 0, logistics_reduction: 0, write_off_reduction: 0, retained_sale_share: 0.65,
      prevention_spend: 0, category_overrides: {},
    });
    expect(q.category_overrides).toBeUndefined();
  });
});
