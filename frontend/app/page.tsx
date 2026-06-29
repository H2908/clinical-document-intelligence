import { redirect } from "next/navigation";

export default function RootPage(): never {
  // Authed users: dashboard. Unauthed: marketing landing.
  // The (authed) group already enforces auth for /dashboard, so a
  // signed-in user reaching / will be redirected to /dashboard;
  // otherwise they hit /landing unauthenticated.
  // We check via a "soft" redirect: forward to /landing always, and
  // let the (authed) layout bounce to /login if there's no token.
  // Actually, simpler: forward to /landing always. The dashboard
  // layout itself does the auth check via proxy.ts.
  redirect("/landing");
}
