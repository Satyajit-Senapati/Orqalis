import { duration } from "./api";
import type { ProviderStats } from "./types";
import { count, Empty } from "./ui";

export function ProviderMetrics({ providers }: { providers: ProviderStats[] }) {
  return (
    <section className="panel operational-panel" aria-label="Provider performance">
      <div className="section-heading">
        <h2>Provider performance</h2>
        <span>Observed calls in this run</span>
      </div>
      <p className="panel-body">
        Call success measures provider execution, not acceptance of the work.
        Latencies use completed calls; token and cost totals include reported values only.
      </p>
      {!providers.length ? <Empty>No provider measurements recorded.</Empty> : (
        <div className="table-scroll">
          <table>
            <caption className="sr-only">Provider outcomes, latency, and reporting coverage</caption>
            <thead><tr>
              <th>Provider / model</th><th>Outcomes</th><th>Latency</th>
              <th>Tokens</th><th>Reported cost</th><th>Errors</th>
            </tr></thead>
            <tbody>{providers.map((provider) => (
              <tr key={JSON.stringify([provider.provider, provider.model])}>
                <th scope="row">{provider.provider}<br />{provider.model}</th>
                <td>
                  {provider.succeeded} succeeded / {provider.calls} calls<br />
                  {provider.failed} failed; {provider.running} running<br />
                  {provider.cancelled} cancelled; {provider.interrupted} interrupted
                </td>
                <td>
                  p50 {provider.p50_latency_ms == null ? "Not reported" : duration(provider.p50_latency_ms)}<br />
                  p95 {provider.p95_latency_ms == null ? "Not reported" : duration(provider.p95_latency_ms)}<br />
                  {provider.calls_with_latency}/{provider.calls} measured
                </td>
                <td>
                  {count(provider.reported_input_tokens)} in / {count(provider.reported_output_tokens)} out<br />
                  {provider.calls_with_usage}/{provider.calls} with usage
                </td>
                <td>
                  {provider.reported_cost_usd == null ? "Not reported" : `$${provider.reported_cost_usd.toFixed(4)}`}<br />
                  {provider.calls_with_cost}/{provider.calls} with cost
                </td>
                <td>{Object.entries(provider.errors).map(([error, total]) => `${error}: ${total}`).join(", ") || "None recorded"}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
    </section>
  );
}
