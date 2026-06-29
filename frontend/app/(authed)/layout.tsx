"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getUser, logout } from "@/lib/auth";

export default function AuthedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [displayName, setDisplayName] = useState<string>("");
  const [email, setEmail] = useState<string>("");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const u = getUser();
    if (u) {
      setDisplayName(u.display_name);
      setEmail(u.email);
    } else {
      // Should never happen — proxy.ts gates /dashboard — but if it does
      // because the JWT cookie expired and we haven't refreshed yet,
      // bounce to login.
      const next = encodeURIComponent(pathname || "/dashboard");
      router.replace(`/login?next=${next}`);
    }
  }, [pathname, router]);

  const handleLogout = () => {
    logout();
    router.replace("/landing");
  };

  return (
    <div className="min-h-screen flex flex-col bg-nhs-pale">
      <header className="bg-nhs-blue text-white">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="border-2 border-white text-white text-xs font-bold px-1.5 py-0.5 leading-none tracking-widest">
              NHS
            </span>
            <div>
              <h1 className="text-lg font-semibold leading-tight">
                Clinical Document Intelligence
              </h1>
              <p className="text-xs text-white/70 mt-0.5">
                Administrative document structuring · For clinical review only
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <Link
              href="/landing"
              className="hidden sm:inline text-white/80 hover:text-white text-xs"
            >
              About
            </Link>
            <div className="relative">
              <button
                onClick={() => setOpen((o) => !o)}
                className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 transition-colors flex items-center gap-2"
                aria-haspopup="menu"
                aria-expanded={open}
              >
                <span className="font-medium text-white truncate max-w-[160px]">
                  {displayName || "Account"}
                </span>
                <span className="text-white/60 text-xs">▾</span>
              </button>
              {open && (
                <div
                  role="menu"
                  className="absolute right-0 mt-2 w-56 bg-white text-slate-900 rounded-lg border border-slate-200 shadow-lg overflow-hidden z-30"
                  onMouseLeave={() => setOpen(false)}
                >
                  <div className="px-4 py-3 border-b border-slate-100">
                    <div className="text-sm font-medium text-slate-900 truncate">
                      {displayName}
                    </div>
                    <div className="text-xs text-slate-500 truncate">{email}</div>
                  </div>
                  <button
                    onClick={handleLogout}
                    className="w-full text-left px-4 py-2.5 text-sm text-nhs-red hover:bg-nhs-red-light transition-colors"
                  >
                    Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>
      {children}
    </div>
  );
}
