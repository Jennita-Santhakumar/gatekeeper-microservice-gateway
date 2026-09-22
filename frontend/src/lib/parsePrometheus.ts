/**
 * Parser for the Prometheus text exposition format
 * (https://github.com/prometheus/docs/blob/main/content/docs/instrumenting/exposition_formats.md).
 *
 * Handles:
 *  - `# HELP` / `# TYPE` / arbitrary `#` comment lines (skipped for values)
 *  - metric lines with no labels: `gateway_requests_total 17`
 *  - metric lines with one or more labels: `http_requests_total{method="GET",status="200"} 42`
 *  - integer and floating point values, including scientific notation
 *  - special values `NaN`, `+Inf`, `-Inf` (and bare `Inf`) per the spec
 *  - an optional trailing timestamp, which is ignored
 *  - commas inside quoted label values (not treated as label separators)
 *  - escaped characters inside quoted label values: `\"`, `\\`, `\n`
 */

export interface PrometheusMetric {
  name: string;
  labels: Record<string, string>;
  value: number;
}

function unescapeLabelValue(raw: string): string {
  let result = "";
  for (let i = 0; i < raw.length; i++) {
    const ch = raw[i];
    if (ch === "\\" && i + 1 < raw.length) {
      const next = raw[i + 1];
      if (next === "n") {
        result += "\n";
        i++;
        continue;
      }
      if (next === '"' || next === "\\") {
        result += next;
        i++;
        continue;
      }
      // Unknown escape sequence: keep the backslash literally, per spec
      // guidance for tolerant parsers.
      result += ch;
      continue;
    }
    result += ch;
  }
  return result;
}

/**
 * Splits the raw contents of a `{...}` label block (without the braces)
 * into individual `key="value"` segments, respecting quoted strings so a
 * comma inside a label value is not mistaken for a label separator.
 */
function splitLabelSegments(labelBody: string): string[] {
  const segments: string[] = [];
  let current = "";
  let inQuotes = false;
  let escaped = false;

  for (const ch of labelBody) {
    if (escaped) {
      current += ch;
      escaped = false;
      continue;
    }
    if (ch === "\\" && inQuotes) {
      current += ch;
      escaped = true;
      continue;
    }
    if (ch === '"') {
      inQuotes = !inQuotes;
      current += ch;
      continue;
    }
    if (ch === "," && !inQuotes) {
      segments.push(current);
      current = "";
      continue;
    }
    current += ch;
  }
  if (current.trim().length > 0) segments.push(current);
  return segments;
}

function parseLabels(labelBody: string): Record<string, string> {
  const labels: Record<string, string> = {};
  const segments = splitLabelSegments(labelBody);

  for (const segment of segments) {
    const trimmed = segment.trim();
    if (!trimmed) continue;
    const eq = trimmed.indexOf("=");
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq).trim();
    let value = trimmed.slice(eq + 1).trim();
    if (value.startsWith('"') && value.endsWith('"') && value.length >= 2) {
      value = unescapeLabelValue(value.slice(1, -1));
    }
    labels[key] = value;
  }

  return labels;
}

function parseValue(token: string): number {
  switch (token) {
    case "NaN":
      return NaN;
    case "+Inf":
    case "Inf":
      return Infinity;
    case "-Inf":
      return -Infinity;
    default:
      return Number(token);
  }
}

/**
 * Locates the balanced `{...}` label block that immediately follows the
 * metric name, returning its inner contents and the index right after the
 * closing brace. Braces are only ever meaningful outside of quoted label
 * values, so quote state is tracked while scanning for the matching `}`.
 */
function extractLabelBlock(line: string, openBraceIndex: number): { body: string; endIndex: number } | null {
  let depth = 0;
  let inQuotes = false;
  let escaped = false;

  for (let i = openBraceIndex; i < line.length; i++) {
    const ch = line[i];
    if (escaped) {
      escaped = false;
      continue;
    }
    if (ch === "\\" && inQuotes) {
      escaped = true;
      continue;
    }
    if (ch === '"') {
      inQuotes = !inQuotes;
      continue;
    }
    if (inQuotes) continue;
    if (ch === "{") depth++;
    if (ch === "}") {
      depth--;
      if (depth === 0) {
        return { body: line.slice(openBraceIndex + 1, i), endIndex: i + 1 };
      }
    }
  }
  return null;
}

function parseLine(line: string): PrometheusMetric | null {
  const trimmed = line.trim();
  if (trimmed.length === 0) return null;
  if (trimmed.startsWith("#")) return null;

  const braceIndex = trimmed.indexOf("{");
  const firstSpace = trimmed.search(/\s/);

  let name: string;
  let labels: Record<string, string> = {};
  let rest: string;

  if (braceIndex !== -1 && (firstSpace === -1 || braceIndex < firstSpace)) {
    name = trimmed.slice(0, braceIndex);
    const block = extractLabelBlock(trimmed, braceIndex);
    if (!block) return null;
    labels = parseLabels(block.body);
    rest = trimmed.slice(block.endIndex).trim();
  } else {
    if (firstSpace === -1) return null;
    name = trimmed.slice(0, firstSpace);
    rest = trimmed.slice(firstSpace).trim();
  }

  if (!name || !rest) return null;

  // rest is `<value>` or `<value> <timestamp>`; the timestamp is ignored.
  const valueToken = rest.split(/\s+/)[0];
  const value = parseValue(valueToken);
  if (Number.isNaN(value) && valueToken !== "NaN") return null;

  return { name, labels, value };
}

export function parsePrometheusText(text: string): PrometheusMetric[] {
  const metrics: PrometheusMetric[] = [];
  const lines = text.split("\n");
  for (const line of lines) {
    const metric = parseLine(line);
    if (metric) metrics.push(metric);
  }
  return metrics;
}
