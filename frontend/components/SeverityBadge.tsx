type Props = {
  severity: "HIGH" | "MEDIUM" | "LOW" | string;
};

export default function SeverityBadge({ severity }: Props) {
  const styles: Record<string, string> = {
    HIGH:   "bg-nhs-red-light   text-nhs-red",
    MEDIUM: "bg-nhs-yellow-light text-[#7a5200]",
    LOW:    "bg-nhs-green-light  text-nhs-green",
  };
  const cls = styles[severity] ?? "bg-slate-100 text-slate-600";
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold tracking-wide ${cls}`}>
      {severity}
    </span>
  );
}
