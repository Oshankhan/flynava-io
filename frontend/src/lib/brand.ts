// IO brand tokens — green/white, matching the FlyNava logo.
export const BRAND = {
  primary: "#157f52",
  primaryStrong: "#0f3f2e",
  accent: "#1ea562",
  green: ["#157f52", "#1ea562", "#34c77b", "#5fd093", "#95e2b8", "#c9f0da"],
};

// RAG → antd colors + labels (single source of truth).
export const RAG = {
  green: { color: "success", label: "On track", hex: "#157f52" },
  amber: { color: "warning", label: "At risk", hex: "#d48806" },
  red: { color: "error", label: "Critical", hex: "#cf1322" },
  grey: { color: "default", label: "No target", hex: "#8c8c8c" },
} as const;
