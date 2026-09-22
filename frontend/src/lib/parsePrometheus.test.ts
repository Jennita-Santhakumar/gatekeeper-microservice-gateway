import { describe, expect, it } from "vitest";

import { parsePrometheusText } from "./parsePrometheus";

describe("parsePrometheusText", () => {
  it("parses metrics with labels", () => {
    const text = [
      "# HELP gateway_requests_total Total requests",
      "# TYPE gateway_requests_total counter",
      'gateway_requests_total{method="GET",endpoint="proxy_users",status="200"} 42',
      'gateway_requests_total{method="POST",endpoint="proxy_posts",status="500"} 3',
    ].join("\n");

    const metrics = parsePrometheusText(text);
    expect(metrics).toHaveLength(2);
    expect(metrics[0]).toEqual({
      name: "gateway_requests_total",
      labels: { method: "GET", endpoint: "proxy_users", status: "200" },
      value: 42,
    });
  });

  it("parses metrics with no labels", () => {
    const metrics = parsePrometheusText("gateway_rate_limit_hits 7");
    expect(metrics).toEqual([{ name: "gateway_rate_limit_hits", labels: {}, value: 7 }]);
  });

  it("ignores comment and blank lines", () => {
    const metrics = parsePrometheusText("# just a comment\n\n# TYPE foo counter\n");
    expect(metrics).toHaveLength(0);
  });

  it("handles a trailing timestamp", () => {
    const metrics = parsePrometheusText("gateway_requests_total 5 1700000000000");
    expect(metrics[0].value).toBe(5);
  });

  it("handles special float values", () => {
    expect(parsePrometheusText("foo NaN")[0].value).toBeNaN();
    expect(parsePrometheusText("foo +Inf")[0].value).toBe(Infinity);
    expect(parsePrometheusText("foo -Inf")[0].value).toBe(-Infinity);
  });

  it("handles commas inside quoted label values", () => {
    const metrics = parsePrometheusText('foo{path="/a,b/c"} 1');
    expect(metrics[0].labels.path).toBe("/a,b/c");
  });

  it("unescapes quoted label values", () => {
    const metrics = parsePrometheusText('foo{msg="line\\nbreak and \\"quote\\""} 1');
    expect(metrics[0].labels.msg).toBe('line\nbreak and "quote"');
  });
});
