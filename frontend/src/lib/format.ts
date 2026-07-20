export function formatValue(value: number | null, unit?: string): string {
  if (value === null || value === undefined) return "—";
  if (unit === "%") return `${value}%`;
  if (unit === "USD") return `$${value.toLocaleString()}`;
  return value.toLocaleString();
}

// Indian-numbering rupee formatter (Cr/L) — the Indicator Of Success screens'
// backend sends raw rupee amounts; the crossover points below match how a
// FlyNava P&L is actually read (nobody reads "₹1,24,50,000", they read "₹12.45 Cr").
export function formatINR(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  const CRORE = 10_000_000;
  const LAKH = 100_000;
  if (abs >= CRORE) return `${sign}₹${(abs / CRORE).toFixed(2)} Cr`;
  if (abs >= LAKH) return `${sign}₹${(abs / LAKH).toFixed(2)} L`;
  return `${sign}₹${abs.toLocaleString("en-IN")}`;
}

// Renders a "Indicator Of Success" SuccessCard value by its backend-declared unit.
export function formatSuccessValue(value: number | null | undefined, unit: string): string {
  if (value === null || value === undefined) return "—";
  switch (unit) {
    case "inr":
      return formatINR(value);
    case "pct":
      return `${value}%`;
    case "hours":
      return `${value} Hrs`;
    case "years":
      return `${value} Yrs`;
    case "ratio":
      return value.toFixed(2);
    case "count":
      return Math.round(value).toLocaleString();
    default:
      return value.toLocaleString();
  }
}
