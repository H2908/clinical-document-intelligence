/**
 * lib/auth.ts — JWT-in-localStorage auth helpers for the Patient/Doctor UI.
 *
 * Architecture:
 *   - On successful /auth/register or /auth/login, the backend returns
 *     { token, user }. We store `token` in localStorage and `user` in
 *     a separate localStorage key so the chrome can render display_name
 *     without a round trip.
 *   - lib/api.ts reads `getToken()` for the Authorization header.
 *   - frontend/proxy.ts reads a parallel `auth_token` cookie (set
 *     by the layout) to gate /dashboard and /patients/* server-side.
 *
 * The cookie is intentionally NOT HttpOnly so the proxy can read it
 * (proxy.ts runs before the React tree mounts and cannot await a
 * React context). HttpOnly is reserved for a future refresh-token cookie.
 */

export type AuthUser = {
  user_id: string;
  tenant_id: string;
  email: string;
  display_name: string;
  role: "doctor" | "admin" | string;
};

export type AuthResponse = {
  token: string;
  user: AuthUser;
};

const TOKEN_KEY = "auth_token";
const USER_KEY = "auth_user";

function isBrowser(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

export function getToken(): string | null {
  if (!isBrowser()) return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function getUser(): AuthUser | null {
  if (!isBrowser()) return null;
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function setSession(token: string, user: AuthUser): void {
  if (!isBrowser()) return;
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
  // Mirror to a non-HttpOnly cookie so frontend/proxy.ts can read it.
  // 12-hour max-age matches JWT_TTL_SECONDS in api/auth.py.
  document.cookie = `auth_token=${encodeURIComponent(token)}; path=/; max-age=43200; samesite=lax`;
}

export function clearSession(): void {
  if (!isBrowser()) return;
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
  document.cookie = "auth_token=; path=/; max-age=0; samesite=lax";
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${apiBase()}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
    cache: "no-store",
  });
  await throwIfNotOk(res);
  const data = (await res.json()) as AuthResponse;
  setSession(data.token, data.user);
  return data;
}

export async function register(args: {
  token: string;
  email: string;
  password: string;
  display_name: string;
}): Promise<AuthResponse> {
  const res = await fetch(`${apiBase()}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(args),
    cache: "no-store",
  });
  await throwIfNotOk(res);
  const data = (await res.json()) as AuthResponse;
  setSession(data.token, data.user);
  return data;
}

export function logout(): void {
  clearSession();
}

export async function previewInvite(token: string): Promise<{
  valid: boolean;
  tenant_slug?: string;
  tenant_name?: string;
  role?: string;
}> {
  const res = await fetch(`${apiBase()}/auth/invite-preview?token=${encodeURIComponent(token)}`, {
    cache: "no-store",
  });
  if (!res.ok) return { valid: false };
  return (await res.json()) as { valid: boolean };
}

async function throwIfNotOk(res: Response): Promise<void> {
  if (res.ok) return;
  let body: any = {};
  try {
    body = await res.json();
  } catch {
    /* ignore */
  }
  const message =
    body?.error?.message ||
    body?.detail?.error?.message ||
    `Request failed: ${res.status}`;
  const err = new Error(message);
  (err as any).code = body?.error?.code || body?.detail?.error?.code;
  (err as any).status = res.status;
  throw err;
}

function apiBase(): string {
  // Mirror lib/api.ts's NEXT_PUBLIC_API_URL default
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
}

/**
 * Read ?next= from a window URL search string. Used by the login page
 * to redirect after successful sign-in.
 */
export function readNextParam(fallback: string = "/dashboard"): string {
  if (!isBrowser()) return fallback;
  const url = new URL(window.location.href);
  const next = url.searchParams.get("next");
  if (!next) return fallback;
  // Only accept same-origin paths to prevent open-redirect abuse.
  if (!next.startsWith("/") || next.startsWith("//")) return fallback;
  return next;
}