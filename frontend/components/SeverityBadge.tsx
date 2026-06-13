type Props = {
  severity: "HIGH" | "MEDIUM" | "LOW" | string;
};

export default function SeverityBadge({ severity }: Props) {
  const styles: Record<string, string> = {
    HIGH:
      "bg-[var(--severity-high-bg)] text-[var(--severity-high)]",
    MEDIUM:
      "bg-[var(--severity-medium-bg)] text-[var(--severity-medium)]",
    LOW:
      "bg-[var(--severity-low-bg)] text-[var(--severity-low)]",
  };
  const cls = styles[severity] || styles.LOW;
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium tracking-wide ${cls}`}>
      {severity}
    </span>
  );
}