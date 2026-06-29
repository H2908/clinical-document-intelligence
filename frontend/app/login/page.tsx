"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { login, readNextParam } from "@/lib/auth";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email.trim(), password);
      const next = params.get("next") || readNextParam();
      router.push(next.startsWith("/") ? next : "/dashboard");
    } catch (err: any) {
      setError(err?.message || "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
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
          Password
        </label>
        <input
          type="password"
          required
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full px-3 py-2.5 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-nhs-blue focus:border-nhs-blue"
        />
      </div>
      {error && (
        <div className="text-sm text-nhs-red bg-nhs-red-light border border-nhs-red/20 rounded-lg px-3 py-2">
          {error}
        </div>
      )}
      <button
        type="submit"
        disabled={busy || !email || !password}
        className="w-full px-4 py-2.5 rounded-lg bg-nhs-blue text-white text-sm font-medium hover:bg-nhs-blue-dark disabled:bg-slate-300 disabled:cursor-not-allowed transition-colors"
      >
        {busy ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}

export default function LoginPage() {
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
            <h2 className="text-2xl font-semibold text-slate-900">Sign in</h2>
            <p className="text-sm text-slate-500">
              Sign in to your trust account to continue.
            </p>
          </div>
          <Suspense fallback={<div className="text-sm text-slate-400">Loading…</div>}>
            <LoginForm />
          </Suspense>
          <p className="text-sm text-slate-600 text-center pt-2 border-t border-slate-100">
            Don't have an account?{" "}
            <Link href="/register" className="text-nhs-blue font-medium hover:underline">
              Register with an invite
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
