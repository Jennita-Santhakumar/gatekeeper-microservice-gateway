import { useEffect, useState } from "react";

import { ApiError, clearToken, getMetrics, getServicesHealth, type ServiceHealth } from "../lib/api";
import { parsePrometheusText, type PrometheusMetric } from "../lib/parsePrometheus";

const POLL_INTERVAL_MS = 5000;

interface DashboardProps {
  onLogout: () => void;
}

function metricValue(metrics: PrometheusMetric[], name: string): number {
  return metrics.filter((m) => m.name === name).reduce((sum, m) => sum + m.value, 0);
}

function metricsByLabel(metrics: PrometheusMetric[], name: string, label: string): Record<string, number> {
  const result: Record<string, number> = {};
  for (const m of metrics) {
    if (m.name !== name) continue;
    const key = m.labels[label] ?? "unknown";
    result[key] = (result[key] ?? 0) + m.value;
  }
  return result;
}

export function GatewayDashboard({ onLogout }: DashboardProps) {
  const [metrics, setMetrics] = useState<PrometheusMetric[]>([]);
  const [health, setHealth] = useState<ServiceHealth | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const [metricsText, healthData] = await Promise.all([getMetrics(), getServicesHealth()]);
        if (cancelled) return;
        setMetrics(parsePrometheusText(metricsText));
        setHealth(healthData);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          clearToken();
          onLogout();
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to reach the gateway.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [onLogout]);

  const requestsByStatus = metricsByLabel(metrics, "gateway_requests_total", "status");
  const rateLimitHits = metricValue(metrics, "gateway_rate_limit_hits");
  const circuitTrips = metricValue(metrics, "gateway_circuit_breaker_trips");
  const services = health?.services ?? {};

  return (
    <div className="min-h-screen bg-slate-950 px-6 py-8 text-white">
      <div className="mx-auto max-w-5xl">
        <header className="mb-8 flex items-center justify-between">
          <h1 className="text-2xl font-semibold">API Gateway Dashboard</h1>
          <button
            onClick={() => {
              clearToken();
              onLogout();
            }}
            className="rounded-md border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
          >
            Sign out
          </button>
        </header>

        {loading && <p className="text-slate-400">Loading live gateway state...</p>}

        {error && (
          <p role="alert" className="mb-6 rounded-md bg-red-950 px-4 py-3 text-sm text-red-300">
            {error}
          </p>
        )}

        {!loading && !error && (
          <>
            <section className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
              <StatCard label="Rate limit hits" value={rateLimitHits} />
              <StatCard label="Circuit breaker trips" value={circuitTrips} />
              <StatCard label="Downstream services" value={Object.keys(services).length} />
            </section>

            <section className="mb-8">
              <h2 className="mb-3 text-lg font-medium">Requests by status code</h2>
              {Object.keys(requestsByStatus).length === 0 ? (
                <p className="text-sm text-slate-500">No requests recorded yet.</p>
              ) : (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {Object.entries(requestsByStatus).map(([status, count]) => (
                    <div key={status} className="rounded-lg border border-slate-800 bg-slate-900 p-4">
                      <p className="text-xs text-slate-500">status {status}</p>
                      <p className="text-xl font-semibold">{count}</p>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section>
              <h2 className="mb-3 text-lg font-medium">Downstream service health</h2>
              {Object.keys(services).length === 0 ? (
                <p className="text-sm text-slate-500">No downstream services reported.</p>
              ) : (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {Object.entries(services).map(([name, info]) => {
                    const status =
                      typeof info === "object" && info !== null && "status" in info
                        ? String((info as Record<string, unknown>).status)
                        : "unknown";
                    const healthy = status === "healthy" || status === "ok";
                    return (
                      <div
                        key={name}
                        className={`rounded-lg border p-4 ${
                          healthy ? "border-emerald-800 bg-emerald-950/40" : "border-red-800 bg-red-950/40"
                        }`}
                      >
                        <p className="text-sm font-medium capitalize">{name}</p>
                        <p className={`text-xs ${healthy ? "text-emerald-400" : "text-red-400"}`}>{status}</p>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>

            <p className="mt-10 text-xs text-slate-500">
              For distributed traces, open the{" "}
              <a
                href="http://localhost:16687"
                target="_blank"
                rel="noreferrer"
                className="text-sky-400 underline"
              >
                Jaeger UI
              </a>{" "}
              directly -- Jaeger's query API does not send permissive CORS headers by default, so this
              dashboard links out rather than embedding trace data in-page.
            </p>
          </>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-2xl font-semibold">{value}</p>
    </div>
  );
}
