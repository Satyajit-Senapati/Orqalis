import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ProviderMetrics } from "./ProviderMetrics";
import type { ProviderStats } from "./types";

const provider: ProviderStats = {
  provider: "fixture", model: "example", calls: 2, succeeded: 1, failed: 0,
  cancelled: 0, interrupted: 0, running: 1, calls_with_latency: 1,
  p50_latency_ms: 200, p95_latency_ms: 200, calls_with_usage: 1, calls_with_cost: 0,
  reported_input_tokens: 0, reported_output_tokens: null, reported_cost_usd: null, errors: {},
};

describe("provider measurements", () => {
  it("renders unknown values and partial reporting coverage without inventing zero cost", () => {
    const html = renderToStaticMarkup(<ProviderMetrics providers={[provider]} />);
    expect(html).toContain("Not reported");
    expect(html).not.toContain("$0.0000");
    expect(html).toContain("1/2 measured");
    expect(html).toContain("0/2 with cost");
    expect(html).toContain("1 succeeded / 2 calls");
    expect(html).toContain("0 in / Not reported out");
  });
  it("distinguishes a reported zero cost from missing cost and escapes provider labels", () => {
    const html = renderToStaticMarkup(<ProviderMetrics providers={[{
      ...provider, provider: "<script>bad</script>", reported_cost_usd: 0, calls_with_cost: 1,
    }]} />);
    expect(html).toContain("$0.0000");
    expect(html).toContain("1/2 with cost");
    expect(html).not.toContain("<script>");
  });
  it("handles historical snapshots without provider measurements", () => {
    expect(renderToStaticMarkup(<ProviderMetrics providers={[]} />))
      .toContain("No provider measurements recorded.");
  });
});
