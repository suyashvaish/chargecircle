const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export function getToken(): string | null {
  if (typeof window !== "undefined") {
    return localStorage.getItem("chargecircle_token");
  }
  return null;
}

export function setToken(token: string) {
  if (typeof window !== "undefined") {
    localStorage.setItem("chargecircle_token", token);
  }
}

export function clearToken() {
  if (typeof window !== "undefined") {
    localStorage.removeItem("chargecircle_token");
    localStorage.removeItem("chargecircle_user");
  }
}

/** Turns FastAPI error payloads (string or validation list) into one readable sentence. */
function describeError(body: any, status: number): string {
  const d = body?.detail ?? body?.message;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    return d.map((e: any) => `${(e.loc || []).slice(1).join(".") || "field"}: ${e.msg}`).join("; ");
  }
  if (status === 403) return "You are not allowed to do that.";
  if (status === 404) return "We could not find what you asked for.";
  if (status >= 500) return "Something went wrong on our side. Please try again in a moment.";
  return `Request failed (HTTP ${status}).`;
}

export async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${API_URL}${endpoint}`, { ...options, headers });
  } catch {
    throw new ApiError(
      typeof navigator !== "undefined" && !navigator.onLine
        ? "You appear to be offline. Check your connection and try again."
        : "We could not reach ChargeCircle. Check your connection and try again.",
      0
    );
  }

  if (!res.ok) {
    let body: any = null;
    try {
      body = await res.json();
    } catch {
      /* non-JSON error body */
    }
    // An expired or invalid session: clear it and send the user to sign in (not for the login call itself).
    if (res.status === 401 && token && typeof window !== "undefined" && !endpoint.startsWith("/auth/login")) {
      clearToken();
      const next = encodeURIComponent(window.location.pathname);
      window.location.href = `/auth/login?expired=1&redirect=${next}`;
    }
    throw new ApiError(describeError(body, res.status), res.status);
  }
  if (typeof window !== "undefined" && res.headers.get("X-ChargeCircle-Cache") === "stale") {
    window.dispatchEvent(new Event("cc-stale-data")); // answered from the offline cache by the service worker
  }
  return res.json();
}
