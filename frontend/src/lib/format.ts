export function formatValue(value: number | null, unit?: string): string {
  if (value === null || value === undefined) return "—";
  if (unit === "%") return `${value}%`;
  if (unit === "USD") return `$${value.toLocaleString()}`;
  return value.toLocaleString();
}
