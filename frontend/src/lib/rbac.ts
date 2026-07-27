import type { User } from "./api";

// Mirrors backend/app/core/rbac.py's ROLES/MODULES/DEFAULT_LEVEL — kept as
// the single source of truth on the frontend instead of scattering copies
// across pages (Admin.tsx and Layout.tsx used to each keep their own,
// out-of-sync list — both were missing team_lead).
export const ROLES = [
  "super_admin",
  "leadership",
  "manager",
  "team_lead",
  "hr",
  "employee",
  "marketing",
  "investor",
  "partner",
] as const;

export const MODULES = [
  "operations",
  "hr",
  "finance",
  "marketing_sales",
  "recruitment",
  "compliance",
  "customer_support",
  "product_dev",
  "awards",
  "ai_insights",
  "admin_panel",
] as const;

const ROLE_LEVEL: Record<string, number> = {
  super_admin: 4,
  leadership: 4,
  manager: 3,
  hr: 3,
  marketing: 3,
  team_lead: 2,
  employee: 1,
  investor: 0,
  partner: 0,
};

export function levelOf(user: User | null): number {
  if (!user) return 1;
  return typeof user.level === "number" ? user.level : ROLE_LEVEL[user.role] ?? 1;
}

export function rolesOf(user: User | null): string[] {
  if (!user) return [];
  return user.roles && user.roles.length > 0 ? user.roles : [user.role];
}
