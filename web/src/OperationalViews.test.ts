import { describe, expect, it } from "vitest";
import { retainAvailableFilter } from "./OperationalViews";

describe("dynamic activity filters", () => {
  const options = [
    ["READY", "Ready"],
    ["COMPLETED", "Completed"],
  ] as const;

  it("retains a selection while its live option is available", () => {
    expect(retainAvailableFilter("READY", options)).toBe("READY");
  });

  it("clears a selection after its live option disappears", () => {
    expect(retainAvailableFilter("FAILED", options)).toBe("");
  });

  it("keeps the unfiltered state empty", () => {
    expect(retainAvailableFilter("", options)).toBe("");
  });
});
