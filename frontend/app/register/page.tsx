"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { previewInvite, readNextParam, register } from "@/lib/auth";

function pwCheck(pw: string): { ok: boolean; reasons: string[] } {
  const reasons: string[] = [];
  if (pw.length < 10) reasons.push("at least 10 characters");
  if (!/[A-Za-z]/.test(pw)) reasons.push("at least one letter");
  if (!/[0-9]/.test(pw)) reasons.push("at least one digit");
  return { ok: reasons.length === 0, reasons };
}

function RegisterForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [token, setToken] = useState(params.get("invite") || "");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tenant, setTenant] = useState<{
    slug?: string;
    name?: string;
  } | null>(null);
  const [inviteStatus, setInviteStatus] = useState<
    "idle" | "checking" | "valid" | "invalid"
  >("idle");

  // Probe the token whenever it changes (debounced).
  useEffect(() => {
    if (!token || token.length < 8) {
      setTenant(null);
      setInviteStatus("idle");
      return;
    }
    setInviteStatus("checking");
    const t = setTimeout(async () => {
      try {
        const r = await previewInvite(token);
        if (r.valid) {
          setTenant({ slug: r.tenant_slug, name: r.tenant_name });
          setInviteStatus("valid");
        } else {
          setTenant(null);
          setInviteStatus("invalid");
        }
      } catch {
        setTenant(null);
        setInviteStatus("invalid");
      }
    }, 350);
    return () => clearTimeout(t);
  }, [token]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const pw = pwCheck(password);
    if (!pw.ok) {
      setError(`Password must contain ${pw.reasons.join(", ")}.`);
      setBusy(false);
      return;
    }
    try {
      await register({
        token: token.trim(),
        email: email.trim(),
        password,
        display_name: displayName.trim(),
      });
      router.push(readNextParam());
    } catch (err: any) {
      setError(err?.message || "Registration failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1">
          Invite token
        </label>
        <input
          value={token}
          onChange={(e) => setToken(e.target.value)}
          required
          minLength={8}
          className="w-full px-3 py-2.5 rounded-lg border border-slate-300 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-nhs-blue focus:border-nhs-blue"
          placeholder="Paste your invite token here"
        />
        {inviteStatus === "checking" && (
          <p className="text-xs text-slate-500 mt-1">Checking…</p>
        )}
        {inviteStatus === "valid" && tenant && (
          <p className="text-xs text-nhs-green mt-1">
            Binds you to <strong>{tenant.name}</strong> ({tenant.slug}).
          </p>
        )}
        {inviteStatus === "invalid" && (
          <p className="text-xs text-nhs-red mt-1">
            Invite token is invalid, used, or expired.
          </p>
        )}
      </div>
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1">
          Work email
        </label>
        <input
          type="email"
          required
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full px-3 py-2.5 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-nhs-blue focus:border-nhs-blue"
          placeholder="firstname.lastname@nhs.uk"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1">
          Display name
        </label>
        <input
          required
          autoComplete="name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          className="w-full px-3 py-2.5 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-nhs-blue focus:border-nhs-blue"
          placeholder="Dr Alice Patel"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1">
          Password
        </label>
        <input
          type="password"
          required
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full px-3 py-2.5 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-nhs-blue focus:border-nhs-blue"
        />
        <p className="text-xs text-slate-500 mt-1">
          At least 10 characters, with at least one letter and one digit.
        </p>
      </div>
      {error && (
        <div className="text-sm text-nhs-red bg-nhs-red-light border border-nhs-red/20 rounded-lg px-3 py-2">
          {error}
        </div>
      )}
      <button
        type="submit"
        disabled={
          busy ||
          !token ||
          !email ||
          !displayName ||
          !password ||
          inviteStatus === "invalid"
        }
        className="w-full px-4 py-2.5 rounded-lg bg-nhs-blue text-white text-sm font-medium hover:bg-nhs-blue-dark disabled:bg-slate-300 disabled:cursor-not-allowed transition-colors"
      >
        {busy ? "Creating account…" : "Create account"}
      </button>
    </form>
  );
}

export default function RegisterPage() {
  return (
    <div className="min-h-screen flex flex-col bg-nhs-pale">
      <header className="bg-nhs-blue text-white">
        <div className="max-w-md mx-auto px-6 py-4 flex items-center gap-3">
          <span className="border-2 border-white text-white text-xs font-bold px-1.5 py-0.5 leading-none tracking-widest">
            NHS
          </span>
          <h1 className="text-lg font-semibold">Clinical Document Intelligence</h1>
        </div>
      </header>
      <main className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md bg-white rounded-xl border border-slate-200 shadow-sm p-8 space-y-6">
          <div className="space-y-1">
            <h2 className="text-2xl font-semibold text-slate-900">Create account</h2>
            <p className="text-sm text-slate-500">
              Sign-ups are by invite only — your trust admin will have issued you one.
            </p>
          </div>
          <Suspense fallback={<div className="text-sm text-slate-400">Loading…</div>}>
            <RegisterForm />
          </Suspense>
          <p className="text-sm text-slate-600 text-center pt-2 border-t border-slate-100">
            Already have an account?{" "}
            <Link href="/login" className="text-nhs-blue font-medium hover:underline">
              Sign in
            </Link>
          </p>
          <p className="text-center">
            <Link href="/landing" className="text-xs text-slate-500 hover:text-slate-700">
              ← Back to home
            </Link>
          </p>
        </div>
      </main>
    </div>
  );
}
