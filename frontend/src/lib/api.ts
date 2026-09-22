const GATEWAY_URL = import.meta.env.VITE_GATEWAY_URL ?? "http://localhost:8100";

const TOKEN_STORAGE_KEY = "gateway_access_token";

/**
 * Small module-level auth store, backed by localStorage so the session
 * survives a page reload. Not a full auth library on purpose -- this is a
 * single-gateway dashboard, not a multi-tenant app.
 */
let currentToken: string | null =
  typeof localStorage !== "undefined" ? localStorage.getItem(TOKEN_STORAGE_KEY) : null;

export function getToken(): string | null {
  return currentToken;
}

export function setToken(token: string): void {
  currentToken = token;
  try {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } catch {
    // localStorage can throw in private/locked-down browser contexts;
    // the in-memory token still works for the current session.
  }
}

export function clearToken(): void {
  currentToken = null;
  try {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    // see setToken
  }
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function parseErrorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    if (typeof body?.message === "string") return body.message;
    return response.statusText || `Request failed with status ${response.status}`;
  } catch {
    return response.statusText || `Request failed with status ${response.status}`;
  }
}

function authHeaders(): HeadersInit {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const response = await fetch(`${GATEWAY_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorMessage(response));
  }
  const data = (await response.json()) as LoginResponse;
  setToken(data.access_token);
  return data;
}

export interface ServiceHealth {
  gateway: string;
  services: Record<string, unknown>;
}

export async function getServicesHealth(): Promise<ServiceHealth> {
  const response = await fetch(`${GATEWAY_URL}/services/health`, {
    headers: { ...authHeaders() },
  });
  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorMessage(response));
  }
  return (await response.json()) as ServiceHealth;
}

/** Returns the raw Prometheus text exposition body -- caller parses it. */
export async function getMetrics(): Promise<string> {
  const response = await fetch(`${GATEWAY_URL}/metrics`, {
    headers: { ...authHeaders() },
  });
  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorMessage(response));
  }
  return response.text();
}

export { GATEWAY_URL };
