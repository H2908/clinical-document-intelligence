/**
 * proxy.ts — Next.js 16 server-side auth gate.
 *
 * IMPORTANT: this is `proxy.ts`, not `middleware.ts`. Next.js 16 deprecated
 * `middleware.ts` and renamed it to `proxy.ts` — see
 *   frontend/node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/proxy.md
 * > "v16.0.0: Middleware is deprecated and renamed to Proxy."
 *
 * What this file does:
 *   - For every request to /dashboard/* and /patients/*, check for the
 *     `auth_token` cookie. If it's missing or empty, redirect to /login
 *     with ?next=<original-path> so the user lands back where they came
 *     from after authenticating.
 *   - For requests to /landing, /login, /register, /auth/*: pass through
 *     unchanged (the matcher below excludes them).
 *
 * What this file does NOT do:
 *   - Decode or verify the JWT signature. Doing so would require
 *     importing JWT_SECRET into the proxy runtime. Instead, the cookie's
 *     mere presence is a hint; the protected server components / pages
 *     double-check by calling /api/auth/me with `Authorization: Bearer …`.
 *     (Server Components can read the cookie via `cookies()` and fetch
 *     the API directly.)
 *   - Set the cookie. That's done in lib/auth.ts setSession() on login
 *     and register.
 */
import { NextResponse, type NextRequest } from "next/server";

export function proxy(request: NextRequest): NextResponse {
  const { pathname, search } = request.nextUrl;
  const token = request.cookies.get("auth_token")?.value;

  if (!token) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = `?next=${encodeURIComponent(pathname + search)}`;
    return NextResponse.redirect(url);
  }

  // Token present — forward the request, attach the value as a request
  // header so server components / route handlers don't have to re-read
  // the cookie. (Not security-critical: server-side JWT verify still
  // re-runs via /api/auth/me.)
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-auth-token", token);

  return NextResponse.next({ request: { headers: requestHeaders } });
}

export const config = {
  // Run on /dashboard/* and /patients/*. Explicitly exclude:
  //   - /landing, /login, /register (public auth pages)
  //   - /api/* (handled server-side by FastAPI)
  //   - all Next.js internals (_next/*)
  matcher: [
    "/dashboard/:path*",
    "/patients/:path*",
  ],
};
