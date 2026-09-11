import { describe, expect, it } from "vitest";
import { classToken, statusTone } from "./ui";

describe("semantic presentation tokens", () => {
  it.each([
    ["COMPLETED", "success"],
    ["READY", "active"],
    ["FAILED", "failure"],
    ["CANCELLED", "failure"],
    ["HUMAN_REVIEW_REQUIRED", "waiting"],
    ["WAITING_FOR_DEPENDENCY", "waiting"],
    ["PENDING", "quiet"],
    ["SKIPPED", "quiet"],
    ["CHANGE_GUARD", "active"],
    ["MEMORY_FINALIZATION", "active"],
  ])("maps %s to the %s tone", (status, tone) => {
    expect(statusTone(status)).toBe(tone);
  });

  it("normalizes role names before using them as CSS classes", () => {
    expect(classToken("Change Guardian")).toBe("change-guardian");
    expect(classToken("Memory_Curator")).toBe("memory-curator");
    expect(classToken("***")).toBe("unknown");
  });
});
