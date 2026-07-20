export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const TOKEN_KEY = "io_token";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

// Fired on any 401 from an authenticated call — AuthProvider listens for this
// and logs out, which sends the user to /login instead of leaving them on a
// page full of confusing "Not Found"/error alerts from a dead session.
export const SESSION_EXPIRED_EVENT = "io:session-expired";

function reportIfSessionExpired(path: string, status: number) {
  if (status === 401 && !path.startsWith("/auth/")) {
    window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
  }
}

function toQuery(params: Record<string, string | undefined>): string {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v) qs.set(k, v);
  });
  const s = qs.toString();
  return s ? `?${s}` : "";
}

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem(TOKEN_KEY);
  const res = await fetch(`${API_BASE_URL}/api/v1${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(opts.headers ?? {}),
    },
  });
  if (!res.ok) {
    reportIfSessionExpired(path, res.status);
    let msg = res.statusText;
    try {
      msg = (await res.json()).detail ?? msg;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, msg);
  }
  return res.status === 204 ? (null as T) : res.json();
}

// --- Types ---
export interface User {
  user_id: string;
  name: string;
  email: string;
  role: string;
  roles?: string[];
  department?: string;
  status?: string;
  level?: number;
  designation?: string | null;
  team_id?: string | null;
  reports_to?: string | null;
}
export interface LoginResult {
  access_token: string;
  refresh_token: string;
  user: User;
}
export type Rag = "green" | "amber" | "red" | "grey";
export interface Kpi {
  kpi_id: string;
  name: string;
  module: string;
  value: number | null;
  unit?: string;
  target?: number | null;
  direction: "higher" | "lower";
  rag: Rag;
  change_pct?: number | null;
  // last ~12 history points for the card's inline sparkline (present when the
  // KPI has enough history); absent for freshly-seeded KPIs.
  spark?: SeriesPoint[];
}
export interface SeriesPoint {
  t: string;
  v: number;
}
export interface KpiSeries {
  kpi_id: string;
  name: string;
  unit?: string;
  points: SeriesPoint[];
}
export interface BugSlice {
  status: string;
  count: number;
}
export interface ProjectRow {
  project_id: string;
  name: string;
  progress: number;
  expected_progress?: number | null;
  rag: Rag;
}
export interface DashboardPayload {
  key: string;
  title: string;
  kpis: Kpi[];
  projects: ProjectRow[];
  alerts: unknown[];
  series?: KpiSeries[];
  bug_breakdown?: BugSlice[];
  insight_depts?: string[];
  project?: string | null;
}
export interface DashboardLink {
  key: string;
  title: string;
}
export interface AiAnswer {
  answer: string;
  reason: string;
  evidence: string[];
  recommended_action: string;
  confidence: "Low" | "Medium" | "High";
  last_updated: string;
}

export interface AiHistoryTurn {
  q: string;
  a: string;
}

// --- Department AI insights (problem-statement detectors) ---
export type InsightSeverity = "high" | "medium" | "low" | "info";
export interface InsightMetric {
  label: string;
  value: number | string;
  unit?: string;
}
export interface InsightEntity {
  kind: string;
  id?: string | null;
  label?: string | null;
  url?: string | null;
  extra?: Record<string, unknown>;
}
export interface InsightChart {
  kind: "bars";
  points: { label: string; value: number }[];
}
export interface InsightFeedback {
  useful: number;
  not_useful: number;
  mine: boolean | null;
}
export interface InsightCard {
  insight_id: string;
  dept: string;
  title: string;
  severity: InsightSeverity;
  problem: string;
  metrics: InsightMetric[];
  entities: InsightEntity[];
  evidence: string[];
  chart: InsightChart | null;
  answer: string;
  reason: string;
  recommended_action: string;
  confidence: "Low" | "Medium" | "High";
  ai_provider: string;
  generated_at: string;
  feedback: InsightFeedback;
}
export interface InsightsPayload {
  dept: string;
  title: string;
  project?: string | null;
  cards: InsightCard[];
  generated_at: string;
  cached: boolean;
}
export interface InsightProject {
  source_id: string;
  name: string;
  task_count: number;
}

// --- KPI explainability ("how did you come up with this number?") ---
export interface KpiExplainInput {
  label: string;
  value: number | string;
}
export interface KpiExplainEvidence {
  kind: string;
  id?: string | null;
  label?: string | null;
  url?: string | null;
  extra?: Record<string, unknown>;
}
export interface KpiExplainSource {
  system: string;
  collection: string | null;
  live: boolean;
  last_sync: string | null;
  note: string;
}
export interface KpiExplanation {
  kpi_id: string;
  name: string;
  module: string;
  unit?: string;
  target?: number | null;
  direction: "higher" | "lower";
  value: number | null;
  rag: Rag;
  formula_text: string;
  computation: string;
  inputs: KpiExplainInput[];
  evidence: KpiExplainEvidence[];
  source: KpiExplainSource;
  history: SeriesPoint[];
  answer: string;
  reason: string;
  recommended_action: string;
  confidence: "Low" | "Medium" | "High";
  ai_provider: string;
  generated_at: string;
}

export interface NotificationItem {
  notif_id: string;
  type: string;
  title: string;
  body: string;
  status: string;
  created_at: string;
  action_link?: string;
}
export interface Award {
  award_id: string;
  recipient_id: string;
  issuer_id: string;
  category: string;
  title: string;
  description: string;
  awarded_at: string;
  reactions: Record<string, number>;
}
export interface LeaderRow {
  recipient_id: string;
  name: string;
  count: number;
}
export interface KpiDef {
  kpi_id: string;
  name: string;
  module: string;
  formula: string;
  unit?: string;
  target?: number | null;
  direction: string;
}
export interface IoDocument {
  doc_id: string;
  title: string;
  kind: string;
  folder_id?: string | null;
  project_id?: string | null;
  filename: string;
  file_type?: string;
  size: number;
  uploaded_by: string;
  uploaded_by_name?: string;
  status: "draft" | "pending" | "approved" | "rejected";
  created_at: string;
  updated_at?: string;
  decided_by?: string | null;
  comment?: string;
  source?: "upload" | "seed";
  shared_with?: string[];
  starred_by?: string[];
  downloads?: number;
}
export interface Folder {
  folder_id: string;
  name: string;
  description: string;
  category: string;
  roles: string[];
  teams: string[];
  document_count: number;
}
export interface DocStats {
  total_documents: number;
  uploaded_this_month: number;
  marketing_assets: number;
  pending_approval: number;
  total_downloads: number;
  storage_used_bytes: number;
  storage_quota_bytes: number;
}
export type DocTab = "all" | "mine" | "shared" | "starred" | "approvals";
export interface AuditRow {
  actor_id: string | null;
  action: string;
  entity_type?: string;
  entity_id?: string;
  created_at: string;
}
export interface ReportProject {
  source_id: string;
  name: string;
  bug_count: number;
}
export interface BugReportRow {
  op_id: string;
  bug_type: string;
  bug_name: string;
  title: string;
  status: string;
  priority: string;
  assignee: string;
  accountable: string;
  url: string;
}
export interface GenerateResult {
  subject: string;
  intro: string;
  count: number;
  html: string;
}
export interface SendResult {
  status: "sent" | "preview";
  detail: string;
  count: number;
  recipients: string[];
  preview_html: string;
}
// --- Reporting Hub ---
export type ReportDomain =
  | "development" | "qa" | "operations" | "projects" | "marketing"
  | "sales" | "finance" | "hr" | "infrastructure";
export type ReportType = "tabular" | "chart" | "summary" | "dashboard";
export type ReportTab = "my" | "shared" | "all" | "scheduled" | "archived" | "confidential";
export type ReportFrequency = "daily" | "weekly" | "monthly" | "quarterly" | "yearly" | "custom";
export type ReportVisibility = "org" | "restricted" | "private";

export interface ReportSectionSpec {
  kind: string;
  params?: Record<string, unknown>;
  title?: string | null;
}
export interface ReportSection {
  key: string;
  title: string;
  kind: "table" | "chart" | "stats" | "text";
  columns?: { key: string; label: string }[];
  rows?: Record<string, unknown>[];
  series?: { name: string; points: SeriesPoint[] }[];
  stats?: { label: string; value: unknown; unit?: string; delta?: number | null; rag?: string }[];
  text?: string;
}
export interface ReportRun {
  run_id: string;
  report_id: string;
  at: string;
  version: number;
  triggered_by: "manual" | "schedule";
  actor_id: string;
  status: "ok" | "error";
  sections: ReportSection[];
  ai_summary: string | null;
  recipients: string[];
  delivery: { status: "sent" | "preview" | "none"; detail: string };
}
export interface ReportSchedule {
  frequency: ReportFrequency;
  time: string;
  weekday?: number | null;
  day_of_month?: number | null;
  every_n_days?: number | null;
  recipients: string[];
  active: boolean;
  next_run_at: string;
  last_run_at?: string | null;
}
export interface ReportDef {
  report_id: string;
  name: string;
  description: string;
  domain: ReportDomain;
  project_id?: string | null;
  type: ReportType;
  sections: ReportSectionSpec[];
  visibility: ReportVisibility;
  access: { roles: string[]; teams: string[] };
  confidential: boolean;
  allowed_user_ids: string[];
  shared_with: string[];
  recipients: string[];
  schedule: ReportSchedule | null;
  owner_id: string;
  owner_name: string;
  is_mine: boolean;
  archived: boolean;
  downloads: number;
  run_count: number;
  created_at: string;
  updated_at: string;
  seed: boolean;
  last_run_at?: string | null;
  last_run_status?: "ok" | "error" | null;
}
export interface ReportStats {
  total_reports: number;
  total_delta_this_month: number;
  scheduled_reports: number;
  next_schedule: { name: string; frequency: ReportFrequency } | null;
  shared_reports: number;
  total_downloads: number;
  delivery_success_pct: number;
}
export interface ReportTemplate {
  template_id: string;
  name: string;
  description: string;
  domain: ReportDomain;
  type: ReportType;
  sections: ReportSectionSpec[];
}
export interface ReportMeta {
  domains: ReportDomain[];
  types: ReportType[];
  section_kinds: { kind: string; confidential: boolean }[];
  projects: { project_id: string; name: string; code: string }[];
  users: { user_id: string; name: string }[];
}
export interface SavedReportView {
  view_id: string;
  user_id: string;
  name: string;
  filters: Record<string, unknown>;
  created_at: string;
}

export interface Salary {
  gross: number;
  basic: number;
  hra: number;
  allowances: number;
  pf: number;
  tax: number;
  net: number;
}
export interface Payslip extends Salary {
  emp_id: string;
  month: string;
  lop_days: number;
}
export interface Leave {
  leave_id: string;
  emp_id: string;
  type: string;
  from: string;
  to: string;
  days: number;
  status: string;
}
export interface Employee {
  emp_id: string;
  name: string;
  email: string;
  designation: string;
  department: string;
  status: string;
  doj: string;
  leave_balance: Record<string, number>;
  salary: Salary;
}
export interface EmployeeDetail extends Employee {
  payslips: Payslip[];
  leaves: Leave[];
}
export interface AttendanceRow {
  emp_code: string;
  name: string;
  date: string;
  in_time: string;
  out_time: string;
  status: string;
  hours: number | null;
}
export interface AttendanceUpload {
  upload_id: string;
  rows: number;
  summary: { total: number; by_status: Record<string, number> };
  preview: AttendanceRow[];
}
export interface AttendanceSendResult {
  status: "sent" | "preview";
  detail: string;
  count: number;
  summary: { total: number; by_status: Record<string, number> };
  preview_html: string;
}

// --- Workspace / org / tasks / meetings / requests ---
export interface UserLite {
  user_id: string;
  name: string;
  designation?: string | null;
  team_id?: string | null;
  level?: number;
  department?: string | null;
  role?: string;
  reports_to?: string | null;
}
export interface TeamInfo {
  team_id: string;
  name: string;
  department?: string;
  lead?: UserLite | null;
  member_count?: number;
  lead_id?: string;
}
export interface OrgMe {
  user: UserLite;
  level: number;
  team: TeamInfo | null;
  lead: UserLite | null;
  reports: UserLite[];
}
export type TaskBucket = "completed" | "in_progress" | "pending" | "overdue";
export interface TaskRow {
  task_id: string;
  title: string;
  status: string | null;
  bucket: TaskBucket;
  wp_type?: string | null;
  priority?: string | null;
  due_date?: string | null;
  progress: number;
  project: string;
  assignee?: string;
  source?: string;
}
export interface TaskBuckets {
  total: number;
  completed: number;
  in_progress: number;
  pending: number;
  overdue: number;
}
export interface MyTasks {
  rows: TaskRow[];
  buckets: TaskBuckets;
  reopened: TaskRow[];
  // Only present on /tasks/my (OP tasks this user authored) — team_tasks
  // doesn't compute this per-member, so it's absent there.
  authored?: TaskRow[];
}
export interface MemberLoad extends TaskBuckets {
  user_id: string;
  name: string;
}
export interface TeamTasks extends MyTasks {
  members: MemberLoad[];
}
export interface Meeting {
  meeting_id: string;
  title: string;
  agenda?: string;
  start: string;
  end: string;
  location?: string;
  organizer_id: string;
  organizer_name?: string;
  attendee_ids: string[];
  status: string;
}
export interface RequestHistory {
  by: string;
  by_name?: string;
  action: string;
  comment?: string;
  at: string;
  to?: string;
}
export interface IoRequest {
  req_id: string;
  type: string;
  title: string;
  body?: string;
  requester_id: string;
  requester_name?: string;
  approver_id?: string | null;
  status: "pending" | "approved" | "rejected";
  history: RequestHistory[];
  created_at: string;
  decided_at?: string | null;
  leave_type?: string | null;
  from_date?: string | null;
  to_date?: string | null;
  days?: number | null;
}
export interface ActivityItem {
  actor_id?: string | null;
  actor_name: string;
  action: string;
  text: string;
  entity_type?: string;
  at: string;
}
export interface WorkspaceData {
  user: UserLite;
  team: TeamInfo | null;
  lead: { name: string; designation?: string | null } | null;
  buckets: TaskBuckets;
  tasks: TaskRow[];
  reopened: TaskRow[];
  meetings: Meeting[];
  my_requests: IoRequest[];
  inbox_count: number;
  unread_notifications: number;
  activity: ActivityItem[];
}

// --- Phase B: dept-exclusive panels ---
export interface ComplianceItem {
  item_id: string;
  title: string;
  due_date: string;
  owner: string;
  status: "pending" | "overdue";
}
export interface Position {
  pos_id: string;
  title: string;
  dept: string;
  days_open: number;
  candidates: number;
  status: string;
}
export interface PendingLeave {
  leave_id: string;
  emp_id: string;
  emp_name: string;
  department?: string | null;
  type: string;
  from: string;
  to: string;
  days: number;
  status: string;
}

// --- Phase C: department-head workspace ---
export interface DeptTeamSummary {
  team_id: string;
  name: string;
  lead_name: string | null;
  buckets: TaskBuckets;
  reopened_count: number;
  member_count: number;
}
export interface DeptWorkspaceData {
  department: string | null;
  teams: DeptTeamSummary[];
  dept_kpis: Kpi[];
  positions: Position[];
}

// --- Phase D: L4 analytics + org chart ---
export interface DayCount {
  date: string;
  count: number;
}
export interface ActionCount {
  action: string;
  count: number;
}
export interface ActorCount {
  user_id: string;
  name: string;
  count: number;
}
export interface DeptCount {
  department: string;
  count: number;
}
export interface IntegrationStatus {
  source: string;
  status: string | null;
  run_at: string | null;
  records_processed: number | null;
}
export interface AnalyticsSummary {
  window_days: number;
  total_actions: number;
  actions_per_day: DayCount[];
  by_action: ActionCount[];
  top_actors: ActorCount[];
  by_department: DeptCount[];
  integrations: IntegrationStatus[];
}

// --- CEO demo build: org drill-down + exec workspace ---
export interface OrgReportRow extends UserLite {
  team_name?: string | null;
  buckets: TaskBuckets;
  reopened_count: number;
  late_7d: number;
  absent_7d: number;
  pending_requests: number;
  has_reports: boolean;
  project_codes: string[];
}
export interface AttendanceSummary {
  rows: AttendanceRow[];
  late_count: number;
  absent_count: number;
  present_count: number;
  avg_hours: number | null;
}
export interface MemberProject {
  project_id: string;
  code: string;
  name: string;
  current_stage_name?: string | null;
}
export interface UserOverview {
  user: UserLite;
  team: TeamInfo | null;
  lead: UserLite | null;
  buckets: TaskBuckets;
  tasks: TaskRow[];
  reopened: TaskRow[];
  authored: TaskRow[];
  attendance: AttendanceSummary;
  leave_balance: Record<string, number> | null;
  recent_leaves: Leave[];
  pending_docs: IoDocument[];
  meetings: Meeting[];
  activity: { action: string; text: string; at: string }[];
  projects: MemberProject[];
}
export interface DeptHead {
  user_id: string;
  name: string;
  designation?: string | null;
}
export interface DeptRollup {
  dept_id: string;
  name: string;
  head: DeptHead | null;
  teams_count: number;
  member_count: number;
  buckets: TaskBuckets;
  reopened_count: number;
  late_today: number;
}
export interface AutomationScript {
  script_id: string;
  title: string;
  module: string;
  owner: string;
  status: "pending" | "in_review" | "done";
  updated_at: string;
}
export interface AutomationSummary {
  pending: number;
  by_module: Record<string, { pending: number; in_review: number; done: number }>;
  rows: AutomationScript[];
}
export interface ProductDoc {
  pdoc_id: string;
  title: string;
  module: string;
  status: string;
  created_at: string;
}
export interface AttendanceToday {
  present: number;
  late: number;
  absent: number;
  late_names: string[];
}
export interface ExecWorkspaceData {
  key: string;
  title: string;
  kpis: Kpi[];
  projects: ProjectRow[];
  series?: KpiSeries[];
  bug_breakdown?: BugSlice[];
  departments: DeptRollup[];
  automation: AutomationSummary;
  pending_docs: ProductDoc[];
  attendance_today: AttendanceToday;
  inbox_count: number;
  meetings: Meeting[];
  activity: ActivityItem[];
}

// --- Client projects (editable stages) ---
export interface ProjectStage {
  key: string;
  name: string;
  description?: string;
  owner_team?: string;
  status: "done" | "active" | "pending";
  progress: number;
  start_date?: string | null;
  end_date?: string | null;
}
export interface ProjectMember {
  user_id: string;
  name: string;
  designation?: string | null;
  team_id?: string | null;
}
export interface ProjectManager {
  user_id: string;
  name: string;
}
export interface ProjectSummary {
  project_id: string;
  code: string;
  name: string;
  client?: string;
  status: string;
  logo?: string | null;
  description?: string | null;
  engagement?: string | null;
  priority?: string | null;
  start_date?: string | null;
  due_date?: string | null;
  project_manager?: ProjectManager | null;
  current_stage: string;
  current_stage_name?: string | null;
  progress: number;
  expected_progress?: number | null;
  team_ids: string[];
  members: ProjectMember[];
  member_count: number;
  bug_count: number;
  task_count: number;
  open_tasks: number;
}
export interface ProjectTaskRow {
  task_id: string;
  title: string;
  status: string | null;
  wp_type?: string | null;
  priority?: string | null;
  assignee_id?: string | null;
  assignee?: string | null;
  progress: number;
  due_date?: string | null;
  stage?: string | null;
}
export interface ProjectActivityItem {
  action: string;
  actor_name: string;
  meta: Record<string, unknown>;
  at: string;
}
export interface ProjectDetail {
  project_id: string;
  code: string;
  name: string;
  client?: string;
  status: string;
  logo?: string | null;
  description?: string | null;
  engagement?: string | null;
  priority?: string | null;
  start_date?: string | null;
  due_date?: string | null;
  project_manager?: ProjectManager | null;
  current_stage: string;
  stages: ProjectStage[];
  progress: number;
  expected_progress?: number | null;
  owner: { user_id: string; name: string } | null;
  team_ids: string[];
  members: ProjectMember[];
  tasks: ProjectTaskRow[];
  bugs: ProjectTaskRow[];
  contract_value?: number | null;
}

// --- CRM: per-project airline contacts (marketing) + billing (finance) ---
export type ContactType = "primary" | "technical" | "business" | "finance" | "other";
export type ContactStatus = "active" | "inactive";
export interface CrmContact {
  contact_id: string;
  project_id: string;
  name: string;
  title?: string;
  department?: string;
  email?: string;
  phone?: string;
  linkedin?: string;
  contact_type: ContactType;
  status: ContactStatus;
  last_contact?: string | null;
  notes?: string;
}
export type InvoiceStatus = "paid" | "pending" | "overdue";
export interface ProjectInvoice {
  invoice_id: string;
  project_id: string;
  number: string;
  date: string;
  due_date?: string | null;
  amount: number;
  currency: string;
  status: InvoiceStatus;
  description?: string;
}
export interface ProjectBilling {
  contract_value: number | null;
  currency: string;
  invoiced: number;
  paid: number;
  outstanding: number;
  invoices: ProjectInvoice[];
}

async function uploadReq<T>(path: string, form: FormData): Promise<T> {
  const token = localStorage.getItem(TOKEN_KEY);
  const res = await fetch(`${API_BASE_URL}/api/v1${path}`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form, // browser sets multipart Content-Type + boundary
  });
  if (!res.ok) {
    reportIfSessionExpired(path, res.status);
    let msg = res.statusText;
    try {
      msg = (await res.json()).detail ?? msg;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, msg);
  }
  return res.json();
}

// --- Indicator Of Success ---
export interface SuccessCard {
  id: string;
  label: string;
  value: number | null;
  unit: string;
  delta_pct: number | null;
  delta_direction: "up" | "down" | "flat" | null;
  good: boolean | null;
  spark?: SeriesPoint[];
  link?: string;
}
export interface SuccessSlice {
  label: string;
  value: number;
}
export interface CentralPayload {
  month: string;
  period: { from: string; to: string };
  cards: SuccessCard[];
  charts: {
    visitors: {
      points: { t: string; visitors: number; interactions: number }[];
      footer: { total_visitors: number; total_interactions: number; engagement_rate: number };
    };
    progress: { slices: SuccessSlice[]; overall_pct: number | null };
  };
  tables: {
    timeline: {
      milestone_id: string;
      name: string;
      sublabel: string;
      date: string;
      status: "Completed" | "In Progress" | "Upcoming";
      order: number;
    }[];
    mini_cards: SuccessCard[];
  };
  last_updated: string;
}
export interface OrgDeptRow {
  dept: string;
  headcount: number;
  performance: number;
  attrition: number;
  trend: number[];
}
export interface OrgPayload {
  month: string;
  cards: SuccessCard[];
  charts: {
    headcount_trend: { points: SeriesPoint[] };
    dept_headcount: { slices: SuccessSlice[] };
    attrition_trend: { points: SeriesPoint[] };
    demographics: {
      gender: { label: string; count: number }[];
      age: { band: string; count: number }[];
      education: { level: string; count: number }[];
    };
  };
  tables: { top_departments: OrgDeptRow[] };
  last_updated: string;
}
export interface MarketingCampaignRow {
  name: string;
  leads: number;
  conv_rate: number;
  roi: number;
  status: string;
}
export interface MarketingChannelRow {
  channel: string;
  impressions: number;
  clicks: number;
  ctr: number;
  leads: number;
  conv_rate: number;
  cost: number;
  cpl: number;
  roi: number;
}
export interface MarketingPayload {
  month: string;
  cards: SuccessCard[];
  charts: {
    leads_by_source: { slices: SuccessSlice[] };
    leads_trend: { points: SeriesPoint[] };
  };
  tables: {
    leads_by_source: { source: string; leads: number }[];
    top_campaigns: MarketingCampaignRow[];
    channels: MarketingChannelRow[];
  };
  last_updated: string;
}
export interface FinanceSummaryRow {
  metric: string;
  current: number | null;
  previous: number | null;
  change: number | null;
  change_pct: number | null;
}
export interface FinancePayload {
  month: string;
  granularity: "monthly" | "yearly";
  cards: SuccessCard[];
  charts: {
    net_cash_flow_trend: { points: SeriesPoint[] };
    revenue_growth_trend: { points: SeriesPoint[] };
    current_ratio_trend: { points: SeriesPoint[] };
  };
  tables: {
    financial_summary: FinanceSummaryRow[];
    revenue_segments: { segment: string; amount: number }[];
    expense_breakdown: { category: string; amount: number }[];
  };
  last_updated: string;
}
export interface StartupKpiRow {
  metric: string;
  current: number | null;
  previous: number | null;
  change: number | null;
  change_pct: number | null;
  spark: SeriesPoint[] | null;
}
export interface StartupPayload {
  month: string;
  cards: SuccessCard[];
  charts: {
    mrr_trend: { points: SeriesPoint[] };
    dau_trend: { points: SeriesPoint[]; average: number };
    cac_trend: { points: SeriesPoint[] };
  };
  tables: { kpi_overview: StartupKpiRow[] };
  last_updated: string;
}
export interface OpsProcessRow {
  process: string;
  total_tasks: number;
  completed: number;
  on_time_pct: number;
  overdue: number;
  avg_completion_hours: number;
  status: "Good" | "Attention";
}
export interface OpsEfficiencyRow {
  metric: string;
  value: number | null;
  delta_pct: number | null;
}
export interface OpsPayload {
  month: string;
  cards: SuccessCard[];
  charts: {
    by_status: { slices: SuccessSlice[] };
    by_priority: { slices: SuccessSlice[] };
    tasks_trend: { points: SeriesPoint[] };
  };
  tables: {
    by_status: { status: string; count: number }[];
    by_priority: { priority: string; count: number }[];
    top_processes: OpsProcessRow[];
    efficiency: OpsEfficiencyRow[];
  };
  last_updated: string;
}

// --- Financial Forecaster ---
export interface ForecasterCard extends SuccessCard {
  band?: string;
  category?: string;
}
export interface ForecasterAlert {
  severity: "high" | "medium" | "low";
  title: string;
  detail: string;
}
export interface ForecasterOverviewPayload {
  month: string;
  cards: ForecasterCard[];
  panels: {
    revenue: {
      this_month: number | null;
      mom_pct: number | null;
      forecast_this_month: number | null;
      vs_forecast_pct: number | null;
      trend: SeriesPoint[];
    };
    workforce: {
      total_employees: number | null;
      new_joiners: number | null;
      resigned: number | null;
      conversion_rate: number | null;
      trend: SeriesPoint[];
    };
    costs: {
      total_expenses: number | null;
      mom_pct: number | null;
      top_categories: { category: string; amount: number }[];
    };
    cashflow: {
      cash_balance: number | null;
      net_cash_flow: number | null;
      trend: SeriesPoint[];
    };
    analyzer: {
      pending_count: number | null;
      overdue_amount: number | null;
      upcoming_due_7d: number | null;
      success_rate: number | null;
      status_breakdown: { status: string; pct: number }[];
    };
  };
  insights: string[];
  alerts: ForecasterAlert[];
  forecast_cards: ForecasterCard[];
  forecast_label: string;
  last_updated: string;
}
export interface ForecasterDeptRow {
  dept: string;
  headcount: number;
  performance: number;
  attrition: number;
  trend: number[];
}
export interface ForecasterWorkforcePayload {
  month: string;
  cards: ForecasterCard[];
  charts: {
    headcount_forecast: { actual: SeriesPoint[]; forecast: SeriesPoint[] };
    joiners_vs_resigned: { joiners: SeriesPoint[]; resigned: SeriesPoint[] };
  };
  tables: { departments: ForecasterDeptRow[] };
  last_updated: string;
}
export interface ForecasterRevenueRow {
  month: string;
  actual: number | null;
  forecast: number | null;
  variance_pct: number | null;
}
export interface ForecasterRevenuePayload {
  month: string;
  cards: ForecasterCard[];
  charts: { revenue_trend: { actual: SeriesPoint[]; forecast: SeriesPoint[] } };
  tables: {
    actual_vs_forecast: ForecasterRevenueRow[];
    revenue_segments: { segment: string; amount: number }[];
  };
  last_updated: string;
}
export interface ForecasterCashflowPayload {
  month: string;
  cards: ForecasterCard[];
  charts: {
    cash_in_vs_out: { bars: { t: string; cash_in: number | null; cash_out: number | null }[] };
    cash_balance_forecast: { actual: SeriesPoint[]; forecast: SeriesPoint[] };
  };
  last_updated: string;
}
export interface ForecasterCategoryRow {
  category: string;
  amount: number;
  previous: number | null;
  change_pct: number | null;
}
export interface ForecasterCostsPayload {
  month: string;
  cards: ForecasterCard[];
  charts: { expense_trend: { actual: SeriesPoint[]; forecast: SeriesPoint[] } };
  tables: { categories: ForecasterCategoryRow[] };
  last_updated: string;
}
export interface ForecasterInvoiceRow {
  invoice_id: string;
  number: string;
  project: string;
  date: string;
  due_date: string;
  amount: number;
  status: string;
}
export interface ForecasterAnalyzerPayload {
  month: string;
  cards: ForecasterCard[];
  charts: {
    status_breakdown: { slices: SuccessSlice[] };
    success_rate_trend: { points: SeriesPoint[] };
  };
  tables: { invoices: ForecasterInvoiceRow[] };
  last_updated: string;
}

// --- Management Overview: Project Bugs Tracker + Project Report ---
export interface ManagementBugProject {
  project: string;
  name: string;
}
export interface ManagementBugRow {
  bug_id: string | null;
  project: string;
  title: string | null;
  severity: string;
  status: string | null;
  assignee: string;
  reported_on: string | null;
  age_days: number | null;
}
export interface ManagementActivityRow {
  kind: "created" | "status_change";
  bug_id: string | null;
  project: string;
  detail: string;
  at: string;
}
export interface ManagementBugsPayload {
  window: { from: string; to: string };
  projects: ManagementBugProject[];
  cards: SuccessCard[];
  charts: {
    creation_trend: { points: { t: string; created: number; resolved: number }[] };
    by_status: { slices: SuccessSlice[] };
    by_severity: { slices: SuccessSlice[] };
    resolution_time_trend: { points: SeriesPoint[] };
  };
  tables: {
    by_status: { status: string; count: number; pct: number }[];
    by_module: { module: string; count: number; pct: number }[];
    recent_unresolved: ManagementBugRow[];
    recent_activity: ManagementActivityRow[];
  };
  last_updated: string;
}
export interface ManagementProjectOption {
  project_id: string;
  name: string;
}
export interface ManagementStage {
  key: string;
  name: string;
  description?: string;
  status: "done" | "active" | "pending";
  progress: number;
  start_date: string | null;
  end_date: string | null;
  owner_team?: string;
}
export interface ManagementReportPayload {
  project: {
    project_id: string;
    code: string;
    name: string;
    client?: string | null;
    status: string;
    engagement?: string | null;
    priority?: string | null;
    start_date?: string | null;
    due_date?: string | null;
    project_manager: { user_id: string; name: string } | null;
    progress: number;
    expected_progress: number | null;
    rag: Rag;
    member_count: number;
  };
  stages: ManagementStage[];
  stats: {
    tasks_total: number;
    tasks_done: number;
    task_completion_pct: number | null;
    bugs_total: number;
    bugs_open: number;
    bugs_critical: number;
    bug_resolution_pct: number | null;
  };
  invoices: {
    paid: number;
    pending: number;
    overdue: number;
    rows: ProjectInvoice[];
  };
  last_updated: string;
}

export const api = {
  login: (email: string, password: string) =>
    req<LoginResult>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => req<{ user: User; modules: Record<string, string> }>("/auth/me"),
  listDashboards: () => req<DashboardLink[]>("/dashboards"),
  getDashboard: (key: string, project?: string | null) =>
    req<DashboardPayload>(`/dashboards/${key}${project ? `?project=${project}` : ""}`),
  askIO: (question: string, history?: AiHistoryTurn[]) =>
    req<AiAnswer>("/ai/ask", {
      method: "POST",
      body: JSON.stringify({ question, history }),
    }),
  explainKpi: (kpiId: string) => req<KpiExplanation>(`/kpis/${kpiId}/explain`),
  insightProjects: () => req<InsightProject[]>("/insights/projects"),
  insights: (dept: string, project?: string | null) =>
    req<InsightsPayload>(`/insights/${dept}${project ? `?project=${project}` : ""}`),
  refreshInsights: (dept: string, project?: string | null) =>
    req<InsightsPayload>(`/insights/${dept}/refresh${project ? `?project=${project}` : ""}`, {
      method: "POST",
    }),
  insightFeedback: (insightId: string, useful: boolean) =>
    req<InsightFeedback & { insight_id: string }>("/insights/feedback", {
      method: "POST",
      body: JSON.stringify({ insight_id: insightId, useful }),
    }),

  // Notifications
  notifications: () => req<NotificationItem[]>("/notifications"),
  unreadCount: () => req<{ count: number }>("/notifications/unread_count"),
  markRead: (id: string) =>
    req<{ status: string }>(`/notifications/${id}/read`, { method: "POST" }),

  // Awards
  awards: () => req<Award[]>("/awards"),
  awardLeaderboard: () => req<LeaderRow[]>("/awards/leaderboard"),
  awardCategories: () => req<string[]>("/awards/categories"),
  createAward: (body: {
    recipient_id: string;
    title: string;
    description: string;
    category: string;
  }) => req<Award>("/awards", { method: "POST", body: JSON.stringify(body) }),
  reactAward: (id: string, type: string) =>
    req<{ status: string }>(`/awards/${id}/react`, {
      method: "POST",
      body: JSON.stringify({ type }),
    }),

  // Document Management: folders, documents, approval flow
  folders: () => req<Folder[]>("/folders"),
  createFolder: (body: { name: string; description?: string; category?: string;
    roles?: string[]; teams?: string[] }) =>
    req<Folder>("/folders", { method: "POST", body: JSON.stringify(body) }),
  updateFolder: (id: string, body: { name?: string; description?: string;
    category?: string; roles?: string[]; teams?: string[] }) =>
    req<Folder>(`/folders/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  documents: (params?: {
    folderId?: string; projectId?: string; q?: string; fileType?: string;
    docStatus?: string; tab?: DocTab; sort?: "newest" | "oldest" | "name" | "size";
  }) => {
    const qp = new URLSearchParams();
    if (params?.folderId) qp.set("folder_id", params.folderId);
    if (params?.projectId) qp.set("project_id", params.projectId);
    if (params?.q) qp.set("q", params.q);
    if (params?.fileType) qp.set("file_type", params.fileType);
    if (params?.docStatus) qp.set("doc_status", params.docStatus);
    if (params?.tab) qp.set("tab", params.tab);
    if (params?.sort) qp.set("sort", params.sort);
    const qs = qp.toString();
    return req<IoDocument[]>(`/documents${qs ? `?${qs}` : ""}`);
  },
  documentStats: () => req<DocStats>("/documents/stats"),
  uploadDocument: (title: string, kind: string, file: File, opts?: {
    folderId?: string; projectId?: string;
  }) => {
    const form = new FormData();
    form.append("title", title);
    form.append("kind", kind);
    if (opts?.folderId) form.append("folder_id", opts.folderId);
    if (opts?.projectId) form.append("project_id", opts.projectId);
    form.append("file", file);
    return uploadReq<IoDocument>("/documents", form);
  },
  submitDocument: (id: string) => req<IoDocument>(`/documents/${id}/submit`, { method: "POST" }),
  decideDocument: (id: string, decision: "approve" | "reject", comment = "") =>
    req<IoDocument>(`/documents/${id}/${decision}`, {
      method: "POST",
      body: JSON.stringify({ comment }),
    }),
  starDocument: (id: string) =>
    req<{ starred: boolean }>(`/documents/${id}/star`, { method: "POST" }),
  shareDocument: (id: string, userIds: string[]) =>
    req<{ shared: string[] }>(`/documents/${id}/share`, {
      method: "POST",
      body: JSON.stringify({ user_ids: userIds }),
    }),
  deleteDocument: (id: string) =>
    req<{ status: string }>(`/documents/${id}`, { method: "DELETE" }),
  downloadDocument: async (id: string, filename: string): Promise<void> => {
    const token = localStorage.getItem(TOKEN_KEY);
    const res = await fetch(`${API_BASE_URL}/api/v1/documents/${id}/download`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) {
      let msg = res.statusText;
      try {
        msg = (await res.json()).detail ?? msg;
      } catch {
        /* ignore */
      }
      throw new ApiError(res.status, msg);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  },

  // Admin
  kpiDefs: () => req<KpiDef[]>("/admin/kpi-defs"),
  notificationLog: () => req<NotificationItem[]>("/admin/notification-log"),
  auditLog: () => req<AuditRow[]>("/admin/audit"),
  listUsers: () => req<User[]>("/users"),
  createUser: (body: {
    name: string;
    email: string;
    role: string;
    password: string;
  }) => req<User>("/admin/users", { method: "POST", body: JSON.stringify(body) }),
  updateUser: (id: string, body: { role?: string; status?: string }) =>
    req<Record<string, unknown>>(`/admin/users/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  syncIntegration: (source: string) =>
    req<Record<string, unknown>>(`/integrations/${source}/sync`, { method: "POST" }),

  // Bug reports
  reportProjects: () => req<ReportProject[]>("/reports/projects"),
  reportBugs: (project: string, status?: string, priority?: string) => {
    const q = new URLSearchParams({ project });
    if (status) q.set("status", status);
    if (priority) q.set("priority", priority);
    return req<BugReportRow[]>(`/reports/bugs?${q.toString()}`);
  },
  generateReport: (body: {
    bug_ids: string[];
    title: string;
    intro?: string;
    ai_intro?: boolean;
  }) => req<GenerateResult>("/reports/generate", { method: "POST", body: JSON.stringify(body) }),
  sendReport: (body: {
    bug_ids: string[];
    recipients: string[];
    title: string;
    intro: string;
  }) => req<SendResult>("/reports/send", { method: "POST", body: JSON.stringify(body) }),

  // Reporting Hub
  reportMeta: () => req<ReportMeta>("/reports/meta"),
  reportTemplates: () => req<ReportTemplate[]>("/reports/templates"),
  reportStats: () => req<ReportStats>("/reports/stats"),
  reportDefs: (params?: {
    tab?: ReportTab; domain?: string; projectId?: string; type?: string; createdBy?: string;
    q?: string; dateFrom?: string; dateTo?: string; sort?: "recent" | "name" | "last_run" | "downloads";
  }) => {
    const qp = new URLSearchParams();
    if (params?.tab) qp.set("tab", params.tab);
    if (params?.domain) qp.set("domain", params.domain);
    if (params?.projectId) qp.set("project_id", params.projectId);
    if (params?.type) qp.set("type", params.type);
    if (params?.createdBy) qp.set("created_by", params.createdBy);
    if (params?.q) qp.set("q", params.q);
    if (params?.dateFrom) qp.set("date_from", params.dateFrom);
    if (params?.dateTo) qp.set("date_to", params.dateTo);
    if (params?.sort) qp.set("sort", params.sort);
    const qs = qp.toString();
    return req<ReportDef[]>(`/reports/defs${qs ? `?${qs}` : ""}`);
  },
  reportDef: (id: string) => req<ReportDef>(`/reports/defs/${id}`),
  createReportDef: (body: {
    name: string; description?: string; domain: ReportDomain; project_id?: string | null;
    type: ReportType; sections: ReportSectionSpec[]; visibility?: ReportVisibility;
    access?: { roles: string[]; teams: string[] }; confidential?: boolean;
    allowed_user_ids?: string[]; recipients?: string[];
  }) => req<ReportDef>("/reports/defs", { method: "POST", body: JSON.stringify(body) }),
  updateReportDef: (id: string, body: Partial<{
    name: string; description: string; domain: ReportDomain; project_id: string | null;
    type: ReportType; sections: ReportSectionSpec[]; visibility: ReportVisibility;
    access: { roles: string[]; teams: string[] }; confidential: boolean;
    allowed_user_ids: string[]; recipients: string[]; archived: boolean;
  }>) => req<ReportDef>(`/reports/defs/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteReportDef: (id: string) => req<{ status: string }>(`/reports/defs/${id}`, { method: "DELETE" }),
  runReportDef: (id: string, aiSummary = false) =>
    req<ReportRun>(`/reports/defs/${id}/run`, {
      method: "POST", body: JSON.stringify({ ai_summary: aiSummary }),
    }),
  sendReportDef: (id: string, body: { recipients: string[]; message?: string; run_id?: string }) =>
    req<{ status: "sent" | "preview"; detail: string; run_id: string; preview_html: string }>(
      `/reports/defs/${id}/send`, { method: "POST", body: JSON.stringify(body) }),
  shareReportDef: (id: string, userIds: string[]) =>
    req<{ shared: string[] }>(`/reports/defs/${id}/share`, {
      method: "POST", body: JSON.stringify({ user_ids: userIds }),
    }),
  setReportSchedule: (id: string, body: {
    frequency: ReportFrequency; time: string; weekday?: number; day_of_month?: number;
    every_n_days?: number; recipients?: string[]; active?: boolean;
  }) => req<ReportDef>(`/reports/defs/${id}/schedule`, { method: "PUT", body: JSON.stringify(body) }),
  deleteReportSchedule: (id: string) =>
    req<{ status: string }>(`/reports/defs/${id}/schedule`, { method: "DELETE" }),
  scheduledReports: () => req<ReportDef[]>("/reports/scheduled"),
  reportDefRuns: (id: string, limit = 20) =>
    req<Omit<ReportRun, "sections">[]>(`/reports/defs/${id}/runs?limit=${limit}`),
  reportRun: (runId: string) => req<ReportRun>(`/reports/runs/${runId}`),
  exportReportRun: async (runId: string, fmt: "csv" | "xls" | "html", filename: string): Promise<void> => {
    const token = localStorage.getItem(TOKEN_KEY);
    const res = await fetch(`${API_BASE_URL}/api/v1/reports/runs/${runId}/export?fmt=${fmt}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new ApiError(res.status, "export failed");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  },
  reportViews: () => req<SavedReportView[]>("/reports/views"),
  createReportView: (name: string, filters: Record<string, unknown>) =>
    req<SavedReportView>("/reports/views", { method: "POST", body: JSON.stringify({ name, filters }) }),
  deleteReportView: (id: string) =>
    req<{ status: string }>(`/reports/views/${id}`, { method: "DELETE" }),

  // Workspace / org / tasks / meetings / requests
  workspaceMe: () => req<WorkspaceData>("/workspace/me"),
  activityRecent: (limit = 10) => req<ActivityItem[]>(`/activity/recent?limit=${limit}`),
  orgMe: () => req<OrgMe>("/org/me"),
  orgTeams: () => req<TeamInfo[]>("/org/teams"),
  orgTeamMembers: (teamId: string) => req<UserLite[]>(`/org/teams/${teamId}/members`),
  orgUsers: () => req<UserLite[]>("/org/users"),
  myTasks: () => req<MyTasks>("/tasks/my"),
  teamTasks: () => req<TeamTasks>("/tasks/team"),
  createTask: (body: {
    title: string;
    description?: string;
    assignee_id?: string;
    due_date?: string | null;
    priority?: string;
    project_id?: string | null;
    stage?: string | null;
  }) => req<TaskRow>("/tasks", { method: "POST", body: JSON.stringify(body) }),
  myMeetings: (start?: string, end?: string) => {
    const q = new URLSearchParams();
    if (start) q.set("start", start);
    if (end) q.set("end", end);
    const qs = q.toString();
    return req<Meeting[]>(`/meetings/my${qs ? `?${qs}` : ""}`);
  },
  createMeeting: (body: {
    title: string;
    start: string;
    end: string;
    attendee_ids: string[];
    location?: string;
    agenda?: string;
  }) => req<Meeting>("/meetings", { method: "POST", body: JSON.stringify(body) }),
  cancelMeeting: (id: string) =>
    req<{ status: string }>(`/meetings/${id}`, { method: "DELETE" }),
  submitRequest: (body: {
    type: string;
    title: string;
    body?: string;
    attachment_doc_id?: string | null;
    leave_type?: string | null;
    from_date?: string | null;
    to_date?: string | null;
  }) => req<IoRequest>("/requests", { method: "POST", body: JSON.stringify(body) }),
  myRequests: () => req<IoRequest[]>("/requests/my"),
  requestInbox: () => req<IoRequest[]>("/requests/inbox"),
  actRequest: (id: string, action: "approve" | "reject" | "forward", comment = "") =>
    req<IoRequest>(`/requests/${id}/${action}`, {
      method: "POST",
      body: JSON.stringify({ comment }),
    }),

  // HR — directory, self-service, attendance ERP
  hrEmployees: () => req<Employee[]>("/hr/employees"),
  hrEmployee: (id: string) => req<EmployeeDetail>(`/hr/employees/${id}`),
  hrMe: () => req<EmployeeDetail>("/hr/me"),
  hrUploadAttendance: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return uploadReq<AttendanceUpload>("/hr/attendance/upload", form);
  },
  hrSendAttendance: (body: { upload_id: string; recipients: string[]; title: string }) =>
    req<AttendanceSendResult>("/hr/attendance/send", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  hrSampleCsv: async (): Promise<string> => {
    const token = localStorage.getItem(TOKEN_KEY);
    const res = await fetch(`${API_BASE_URL}/api/v1/hr/attendance/sample`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new ApiError(res.status, "sample failed");
    return res.text();
  },

  // Phase B — dept-exclusive panels
  complianceItems: () => req<ComplianceItem[]>("/compliance/items"),
  positions: (dept?: string) => {
    const qs = dept ? `?dept=${dept}` : "";
    return req<Position[]>(`/positions${qs}`);
  },
  kpiHistory: (kpiId: string) => req<KpiSeries>(`/kpis/${kpiId}/history`),
  pendingLeaves: () => req<PendingLeave[]>("/hr/leaves"),
  decideLeave: (id: string, action: "approve" | "reject", comment = "") =>
    req<PendingLeave>(`/hr/leaves/${id}/${action}`, {
      method: "POST",
      body: JSON.stringify({ comment }),
    }),

  // Phase C — department-head workspace
  workspaceDepartment: () => req<DeptWorkspaceData>("/workspace/department"),

  // Phase D — L4 analytics + org chart
  analyticsSummary: (days = 30) =>
    req<AnalyticsSummary>(`/analytics/summary?days=${days}`),

  // CEO demo build — org drill-down + exec workspace
  orgReports: (userId: string) => req<OrgReportRow[]>(`/org/reports/${userId}`),
  userOverview: (userId: string) => req<UserOverview>(`/org/users/${userId}/overview`),
  execWorkspace: () => req<ExecWorkspaceData>("/workspace/exec"),
  // Client projects (editable stages)
  projects: () => req<ProjectSummary[]>("/projects"),
  project: (id: string) => req<ProjectDetail>(`/projects/${id}`),
  createProject: (body: {
    code: string;
    name: string;
    client?: string;
    team_ids?: string[];
    member_ids?: string[];
    description?: string;
    engagement?: string;
    priority?: string;
    project_manager_id?: string | null;
    start_date?: string | null;
    due_date?: string | null;
  }) => req<ProjectSummary>("/projects", { method: "POST", body: JSON.stringify(body) }),
  updateProject: (id: string, body: {
    name?: string;
    client?: string;
    description?: string;
    engagement?: string;
    priority?: string;
    status?: string;
    project_manager_id?: string | null;
    start_date?: string | null;
    due_date?: string | null;
    team_ids?: string[];
  }) => req<ProjectDetail>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  addStage: (id: string, body: {
    key: string;
    name: string;
    description?: string;
    status?: string;
    progress?: number;
    start_date?: string | null;
    end_date?: string | null;
  }) => req<ProjectDetail>(`/projects/${id}/stages`, { method: "POST", body: JSON.stringify(body) }),
  updateStage: (id: string, stageKey: string, body: {
    name?: string;
    description?: string;
    status?: string;
    progress?: number;
    start_date?: string | null;
    end_date?: string | null;
  }) => req<ProjectDetail>(`/projects/${id}/stages/${stageKey}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  }),
  deleteStage: (id: string, stageKey: string) =>
    req<ProjectDetail>(`/projects/${id}/stages/${stageKey}`, { method: "DELETE" }),
  addProjectMembers: (id: string, member_ids: string[]) =>
    req<{ added: string[] }>(`/projects/${id}/members`, {
      method: "POST",
      body: JSON.stringify({ member_ids }),
    }),
  projectActivity: (id: string) => req<ProjectActivityItem[]>(`/projects/${id}/activity`),
  deleteProject: (id: string) => req<{ deleted: string }>(`/projects/${id}`, { method: "DELETE" }),
  // CRM: marketing-only account contacts, per project
  projectContacts: (id: string) => req<CrmContact[]>(`/projects/${id}/contacts`),
  createContact: (id: string, body: {
    name: string;
    title?: string;
    department?: string;
    email?: string;
    phone?: string;
    linkedin?: string;
    contact_type?: ContactType;
    status?: ContactStatus;
    last_contact?: string | null;
    notes?: string;
  }) => req<CrmContact>(`/projects/${id}/contacts`, { method: "POST", body: JSON.stringify(body) }),
  updateContact: (id: string, contactId: string, body: Partial<{
    name: string;
    title: string;
    department: string;
    email: string;
    phone: string;
    linkedin: string;
    contact_type: ContactType;
    status: ContactStatus;
    last_contact: string | null;
    notes: string;
  }>) => req<CrmContact>(`/projects/${id}/contacts/${contactId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  }),
  deleteContact: (id: string, contactId: string) =>
    req<{ deleted: string }>(`/projects/${id}/contacts/${contactId}`, { method: "DELETE" }),
  // CRM: finance-only billing, per project
  projectBilling: (id: string) => req<ProjectBilling>(`/projects/${id}/billing`),
  createInvoice: (id: string, body: {
    number: string;
    date: string;
    due_date?: string | null;
    amount: number;
    currency?: string;
    status?: InvoiceStatus;
    description?: string;
  }) => req<ProjectInvoice>(`/projects/${id}/invoices`, { method: "POST", body: JSON.stringify(body) }),
  updateInvoice: (id: string, invoiceId: string, body: Partial<{
    date: string;
    due_date: string | null;
    amount: number;
    currency: string;
    status: InvoiceStatus;
    description: string;
  }>) => req<ProjectInvoice>(`/projects/${id}/invoices/${invoiceId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  }),

  notificationsStreamUrl: () => {
    const token = localStorage.getItem(TOKEN_KEY);
    return `${API_BASE_URL}/api/v1/notifications/stream?token=${encodeURIComponent(token ?? "")}`;
  },

  // Indicator Of Success
  successCentral: (p?: { month?: string; from?: string; to?: string }) =>
    req<CentralPayload>(
      `/success/central${toQuery({ month: p?.month, from: p?.from, to: p?.to })}`
    ),
  successOrganization: (month?: string) =>
    req<OrgPayload>(`/success/organization${toQuery({ month })}`),
  successMarketing: (month?: string) =>
    req<MarketingPayload>(`/success/marketing${toQuery({ month })}`),
  successFinance: (month?: string, granularity: "monthly" | "yearly" = "monthly") =>
    req<FinancePayload>(`/success/finance${toQuery({ month, granularity })}`),
  successStartup: (month?: string) =>
    req<StartupPayload>(`/success/startup${toQuery({ month })}`),
  successOperations: (month?: string) =>
    req<OpsPayload>(`/success/operations${toQuery({ month })}`),

  // Financial Forecaster
  forecasterOverview: (month?: string) =>
    req<ForecasterOverviewPayload>(`/forecaster/overview${toQuery({ month })}`),
  forecasterWorkforce: (month?: string) =>
    req<ForecasterWorkforcePayload>(`/forecaster/workforce${toQuery({ month })}`),
  forecasterRevenue: (month?: string) =>
    req<ForecasterRevenuePayload>(`/forecaster/revenue${toQuery({ month })}`),
  forecasterCashflow: (month?: string) =>
    req<ForecasterCashflowPayload>(`/forecaster/cashflow${toQuery({ month })}`),
  forecasterCosts: (month?: string) =>
    req<ForecasterCostsPayload>(`/forecaster/costs${toQuery({ month })}`),
  forecasterAnalyzer: (month?: string) =>
    req<ForecasterAnalyzerPayload>(`/forecaster/analyzer${toQuery({ month })}`),

  // Management Overview
  managementBugs: (p?: { preset?: string; from?: string; to?: string; project?: string }) =>
    req<ManagementBugsPayload>(
      `/management/bugs${toQuery({ preset: p?.preset, from: p?.from, to: p?.to, project: p?.project })}`
    ),
  managementReport: (project: string) =>
    req<ManagementReportPayload>(`/management/report${toQuery({ project })}`),
  managementProjects: () => req<ManagementProjectOption[]>("/management/projects"),
};
