"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type NavItem = {
  label: string;
  href: string;
  icon: string;
};

type Props = {
  patientId: string;
  patientName: string;
  patientDob?: string;
  patientNhs?: string;
};

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0]?.toUpperCase() || "")
    .join("");
}

export default function PatientSidebar({
  patientId,
  patientName,
  patientDob,
  patientNhs,
}: Props) {
  const pathname = usePathname();

  const items: NavItem[] = [
    { label: "Overview",       href: `/patients/${patientId}`,                icon: "▦" },
    { label: "Timeline",       href: `/patients/${patientId}/timeline`,       icon: "⌚" },
    { label: "Flags",          href: `/patients/${patientId}/flags`,          icon: "⚑" },
    { label: "Contradictions", href: `/patients/${patientId}/contradictions`, icon: "⇄" },
    { label: "Briefing",       href: `/patients/${patientId}/briefing`,       icon: "📋" },
    { label: "Documents",      href: `/patients/${patientId}/documents`,      icon: "📄" },
  ];

  return (
    <aside className="w-64 bg-white border-r border-slate-200 flex flex-col py-6 px-3 min-h-screen shrink-0">
      <div className="flex items-start gap-3 px-3 pb-5 border-b border-slate-200 mb-3">
        <div className="w-10 h-10 rounded-full bg-blue-50 text-blue-700 flex items-center justify-center font-medium text-sm shrink-0">
          {initials(patientName)}
        </div>
        <div className="min-w-0">
          <div className="font-medium text-slate-900 text-sm truncate">
            {patientName}
          </div>
          {patientDob && (
            <div className="text-xs text-slate-500 mt-0.5">DOB {patientDob}</div>
          )}
          {patientNhs && (
            <div className="text-xs text-slate-500 font-mono mt-1 truncate">
              NHS {patientNhs}
            </div>
          )}
        </div>
      </div>

      <nav className="flex flex-col gap-0.5">
        {items.map((item) => {
          const isActive =
            item.href === `/patients/${patientId}`
              ? pathname === item.href
              : pathname?.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                isActive
                  ? "bg-blue-50 text-blue-700 font-medium"
                  : "text-slate-700 hover:bg-slate-100"
              }`}
            >
              <span className="w-5 text-center text-base">{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}