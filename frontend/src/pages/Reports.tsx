import { useCallback, useEffect, useState } from "react";
import {
  Alert, Avatar, Badge, Button, Card, Col, DatePicker, Dropdown, Empty, Flex, Form, Input,
  Modal, Pagination, Popover, Row, Select, Segmented, Spin, Table, Tabs, Tag, Typography,
  message,
} from "antd";
import {
  CalendarOutlined, CheckCircleOutlined, CloudUploadOutlined, DownloadOutlined, FileProtectOutlined,
  FileTextOutlined, FilterOutlined, PlayCircleOutlined, PlusOutlined, SaveOutlined, SearchOutlined,
  ShareAltOutlined, TableOutlined, TeamOutlined, UnorderedListOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import {
  api, ApiError,
  type ReportDef, type ReportDomain, type ReportMeta, type ReportStats, type ReportTab,
  type ReportTemplate, type SavedReportView, type UserLite,
} from "../lib/api";
import { useAuth } from "../lib/auth";
import { levelOf } from "../components/Layout";
import StatTile from "../components/StatTile";
import ReportWizard from "../components/reports/ReportWizard";
import ReportViewer from "../components/reports/ReportViewer";
import ScheduleModal from "../components/reports/ScheduleModal";

const { Text } = Typography;
const { RangePicker } = DatePicker;

const DOMAIN_CHIP: Record<ReportDomain, string> = {
  development: "green", qa: "purple", operations: "cyan", marketing: "magenta",
  finance: "blue", hr: "gold", infrastructure: "geekblue", sales: "orange", projects: "volcano",
};
// Full literal Tailwind class strings (not built via template interpolation —
// Tailwind's scanner only picks up classes that appear as literal substrings
// in the source, and several antd Tag color names above aren't even valid
// Tailwind palette names).
const DOMAIN_ICON_TINT: Record<ReportDomain, string> = {
  development: "bg-emerald-500/15 text-emerald-600",
  qa: "bg-purple-500/15 text-purple-600",
  operations: "bg-cyan-500/15 text-cyan-600",
  marketing: "bg-pink-500/15 text-pink-600",
  finance: "bg-blue-500/15 text-blue-600",
  hr: "bg-amber-500/15 text-amber-600",
  infrastructure: "bg-indigo-500/15 text-indigo-600",
  sales: "bg-orange-500/15 text-orange-600",
  projects: "bg-rose-500/15 text-rose-600",
};
const TYPE_CHIP: Record<string, string> = {
  tabular: "blue", chart: "purple", summary: "cyan", dashboard: "orange",
};
const FREQ_COLOR: Record<string, string> = {
  daily: "#16a34a", weekly: "#2563eb", monthly: "#7c3aed", quarterly: "#d97706",
  yearly: "#dc2626", custom: "#6b7280",
};
const FREQ_LABEL: Record<string, string> = {
  daily: "Daily", weekly: "Weekly", monthly: "Monthly", quarterly: "Quarterly",
  yearly: "Yearly", custom: "Custom",
};

const TAB_ITEMS: { key: ReportTab; label: string }[] = [
  { key: "my", label: "My Reports" },
  { key: "shared", label: "Shared With Me" },
  { key: "all", label: "All Reports" },
  { key: "scheduled", label: "Scheduled Reports" },
];

export default function Reports() {
  const { user } = useAuth();
  const level = levelOf(user);
  const canSchedule = level >= 2;
  const canConfidential = level >= 3 || user?.role === "hr";

  const [tab, setTab] = useState<ReportTab | "templates">("my");
  const [domain, setDomain] = useState("all");
  const [projectId, setProjectId] = useState("all");
  const [type, setType] = useState("all");
  const [createdBy, setCreatedBy] = useState("all");
  const [dateRange, setDateRange] = useState<[string, string] | null>(null);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<"recent" | "name" | "last_run" | "downloads">("recent");
  const [view, setView] = useState<"list" | "grid">("list");
  const [gridPage, setGridPage] = useState(1);
  const GRID_PAGE_SIZE = 12;

  const [defs, setDefs] = useState<ReportDef[] | null>(null);
  const [stats, setStats] = useState<ReportStats | null>(null);
  const [meta, setMeta] = useState<ReportMeta | null>(null);
  const [templates, setTemplates] = useState<ReportTemplate[]>([]);
  const [savedViews, setSavedViews] = useState<SavedReportView[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [wizardOpen, setWizardOpen] = useState(false);
  const [editingDef, setEditingDef] = useState<ReportDef | null>(null);
  const [initialTemplateId, setInitialTemplateId] = useState<string | null>(null);
  const [viewingDef, setViewingDef] = useState<ReportDef | null>(null);
  const [scheduleDef, setScheduleDef] = useState<ReportDef | null>(null);
  const [shareDef, setShareDef] = useState<ReportDef | null>(null);
  const [people, setPeople] = useState<UserLite[]>([]);
  const [shareForm] = Form.useForm();
  const [sharing, setSharing] = useState(false);
  const [runningId, setRunningId] = useState<string | null>(null);

  const loadDefs = useCallback(() => {
    api.reportDefs({
      tab: tab === "templates" ? "all" : tab,
      domain: domain !== "all" ? domain : undefined,
      projectId: projectId !== "all" ? projectId : undefined,
      type: type !== "all" ? type : undefined,
      createdBy: createdBy !== "all" ? createdBy : undefined,
      q: search || undefined,
      dateFrom: dateRange?.[0], dateTo: dateRange?.[1], sort,
    }).then(setDefs).catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load reports"));
  }, [tab, domain, projectId, type, createdBy, search, dateRange, sort]);
  const loadStats = useCallback(() => {
    api.reportStats().then(setStats).catch(() => setStats(null));
  }, []);

  useEffect(loadDefs, [loadDefs]);
  useEffect(loadStats, [loadStats]);
  useEffect(() => {
    api.reportMeta().then(setMeta).catch(() => setMeta(null));
    api.reportTemplates().then(setTemplates).catch(() => setTemplates([]));
    api.reportViews().then(setSavedViews).catch(() => setSavedViews([]));
  }, []);
  useEffect(() => setGridPage(1), [tab, domain, projectId, type, createdBy, search, dateRange, sort]);
  useEffect(() => {
    if (shareDef) api.orgUsers().then(setPeople).catch(() => setPeople([]));
  }, [shareDef]);

  const refreshAll = useCallback(() => {
    loadDefs();
    loadStats();
  }, [loadDefs, loadStats]);

  async function runRow(id: string) {
    setRunningId(id);
    try {
      await api.runReportDef(id);
      message.success("Report generated");
      refreshAll();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Run failed");
    } finally {
      setRunningId(null);
    }
  }

  async function exportRowCsv(rd: ReportDef) {
    setRunningId(rd.report_id);
    try {
      const run = await api.runReportDef(rd.report_id);
      await api.exportReportRun(run.run_id, "csv", `${rd.name}.csv`);
      refreshAll();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Export failed");
    } finally {
      setRunningId(null);
    }
  }

  async function toggleArchive(rd: ReportDef) {
    try {
      await api.updateReportDef(rd.report_id, { archived: !rd.archived });
      message.success(rd.archived ? "Report restored" : "Report archived");
      refreshAll();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Update failed");
    }
  }

  function confirmDelete(rd: ReportDef) {
    Modal.confirm({
      title: `Delete "${rd.name}"?`,
      content: "This permanently deletes the report and its run history.",
      okText: "Delete", okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await api.deleteReportDef(rd.report_id);
          message.success("Report deleted");
          refreshAll();
        } catch (e) {
          message.error(e instanceof ApiError ? e.message : "Delete failed");
        }
      },
    });
  }

  async function doShare(values: { user_ids: string[] }) {
    if (!shareDef) return;
    setSharing(true);
    try {
      await api.shareReportDef(shareDef.report_id, values.user_ids);
      message.success("Report shared");
      setShareDef(null);
      refreshAll();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Share failed");
    } finally {
      setSharing(false);
    }
  }

  function saveCurrentView() {
    let name = "";
    Modal.confirm({
      title: "Save current view",
      content: <Input placeholder="View name" onChange={(e) => { name = e.target.value; }} />,
      okText: "Save",
      onOk: async () => {
        if (!name.trim()) return message.warning("Give the view a name");
        const view = await api.createReportView(name.trim(), {
          tab, domain, projectId, type, createdBy, dateRange, sort,
        });
        setSavedViews((v) => [view, ...v]);
        message.success("View saved");
      },
    });
  }
  function applyView(v: SavedReportView) {
    const f = v.filters as Record<string, unknown>;
    if (typeof f.tab === "string") setTab(f.tab as ReportTab);
    if (typeof f.domain === "string") setDomain(f.domain);
    if (typeof f.projectId === "string") setProjectId(f.projectId);
    if (typeof f.type === "string") setType(f.type);
    if (typeof f.createdBy === "string") setCreatedBy(f.createdBy);
    if (Array.isArray(f.dateRange)) setDateRange(f.dateRange as [string, string]);
    if (typeof f.sort === "string") setSort(f.sort as typeof sort);
  }

  const pendingCount = stats?.scheduled_reports ?? 0;

  const columns = [
    {
      title: "Report Name", key: "name",
      render: (_: unknown, rd: ReportDef) => (
        <div className="min-w-0 cursor-pointer" onClick={() => setViewingDef(rd)}>
          <Flex align="center" gap={8}>
            <span className={`flex items-center justify-center w-7 h-7 rounded-full shrink-0 ${DOMAIN_ICON_TINT[rd.domain]}`}>
              <FileTextOutlined />
            </span>
            <Text strong className="text-[13px]" ellipsis>{rd.name}</Text>
          </Flex>
          {rd.description && (
            <Text type="secondary" className="text-[11px] block truncate ps-9">{rd.description}</Text>
          )}
        </div>
      ),
    },
    {
      title: "Domain", dataIndex: "domain", key: "domain", width: 120,
      render: (d: ReportDomain) => <Tag color={DOMAIN_CHIP[d]} className="capitalize">{d}</Tag>,
    },
    {
      title: "Project", dataIndex: "project_id", key: "project", width: 140,
      render: (pid: string | null) => {
        const p = meta?.projects.find((pr) => pr.project_id === pid);
        return p ? <Text className="text-[12px]">{p.code}</Text> : <Text type="secondary">—</Text>;
      },
    },
    {
      title: "Type", dataIndex: "type", key: "type", width: 100,
      render: (t: string) => <Tag color={TYPE_CHIP[t] ?? "default"} className="capitalize">{t}</Tag>,
    },
    {
      title: "Created By", key: "owner", width: 130,
      render: (_: unknown, rd: ReportDef) => (
        <Flex align="center" gap={6}>
          <Avatar size="small" className="bg-io-600">{(rd.owner_name ?? "?")[0]}</Avatar>
          <Text className="text-[12px]">{rd.is_mine ? "Me" : rd.owner_name}</Text>
        </Flex>
      ),
    },
    {
      title: "Last Run", key: "last_run", width: 130,
      render: (_: unknown, rd: ReportDef) => rd.last_run_at ? (
        <div>
          <div className="text-[12px]">{new Date(rd.last_run_at).toLocaleDateString()}</div>
          <Text type="secondary" className="text-[11px]">
            {new Date(rd.last_run_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </Text>
        </div>
      ) : <Text type="secondary" className="text-[12px]">Never</Text>,
    },
    {
      title: "Frequency", key: "frequency", width: 110,
      render: (_: unknown, rd: ReportDef) => rd.schedule ? (
        <Flex align="center" gap={6}>
          <span className="w-2 h-2 rounded-full shrink-0" style={{ background: FREQ_COLOR[rd.schedule.frequency] }} />
          <Text className="text-[12px]">{FREQ_LABEL[rd.schedule.frequency]}</Text>
        </Flex>
      ) : <Text type="secondary" className="text-[12px]">—</Text>,
    },
    {
      title: "", key: "actions", width: 110,
      render: (_: unknown, rd: ReportDef) => {
        const canEdit = rd.is_mine || level >= 3;
        const canDelete = rd.is_mine || user?.role === "super_admin";
        return (
          <Flex align="center" gap={2}>
            <Button type="text" size="small" icon={<PlayCircleOutlined />} loading={runningId === rd.report_id}
              onClick={() => runRow(rd.report_id)} title="Run now" />
            <Button type="text" size="small" icon={<ShareAltOutlined />} onClick={() => setShareDef(rd)} title="Share" />
            <Dropdown menu={{
              items: [
                { key: "view", label: "View" },
                canEdit && { key: "edit", label: "Edit" },
                canSchedule && canEdit && { key: "schedule", label: "Schedule" },
                { key: "export", icon: <DownloadOutlined />, label: "Export CSV" },
                canEdit && { key: "archive", label: rd.archived ? "Restore" : "Archive" },
                canDelete && { key: "delete", label: "Delete", danger: true },
              ].filter(Boolean) as { key: string; label: string; danger?: boolean; icon?: React.ReactNode }[],
              onClick: ({ key }) => {
                if (key === "view") setViewingDef(rd);
                else if (key === "edit") { setEditingDef(rd); setWizardOpen(true); }
                else if (key === "schedule") setScheduleDef(rd);
                else if (key === "export") exportRowCsv(rd);
                else if (key === "archive") toggleArchive(rd);
                else if (key === "delete") confirmDelete(rd);
              },
            }}>
              <Button type="text" size="small">⋮</Button>
            </Dropdown>
          </Flex>
        );
      },
    },
  ];

  if (error) return <Alert type="error" message={error} showIcon />;

  const visibleDefs = defs ?? [];
  const paged = view === "grid" ? visibleDefs.slice((gridPage - 1) * GRID_PAGE_SIZE, gridPage * GRID_PAGE_SIZE) : visibleDefs;

  return (
    <div>
      <Flex gap={8} wrap className="mb-4">
        <Input
          placeholder="Search reports..." prefix={<SearchOutlined className="text-gray-400" />}
          value={search} onChange={(e) => setSearch(e.target.value)} className="max-w-xs" allowClear
        />
        <Select value={domain} onChange={setDomain} className="w-40" options={[
          { value: "all", label: "All Domains" },
          ...(meta?.domains ?? []).map((d) => ({ value: d, label: d.charAt(0).toUpperCase() + d.slice(1) })),
        ]} />
        <Select value={projectId} onChange={setProjectId} className="w-40" options={[
          { value: "all", label: "All Projects" },
          ...(meta?.projects ?? []).map((p) => ({ value: p.project_id, label: `${p.name} (${p.code})` })),
        ]} />
        <Select value={type} onChange={setType} className="w-36" options={[
          { value: "all", label: "All Types" },
          ...(meta?.types ?? []).map((t) => ({ value: t, label: t.charAt(0).toUpperCase() + t.slice(1) })),
        ]} />
        <Select value={createdBy} onChange={setCreatedBy} className="w-40" options={[
          { value: "all", label: "Created By: Anyone" },
          ...(meta?.users ?? []).map((u) => ({ value: u.user_id, label: u.name })),
        ]} />
        <Popover trigger="click" title="More Filters" content={
          <RangePicker
            value={dateRange ? [dayjs(dateRange[0]), dayjs(dateRange[1])] : null}
            onChange={(v) => setDateRange(v ? [v[0]!.format("YYYY-MM-DD"), v[1]!.format("YYYY-MM-DD")] : null)}
          />
        }>
          <Button icon={<FilterOutlined />}>More Filters</Button>
        </Popover>
        <div className="flex-1" />
        <Dropdown menu={{
          items: [
            ...savedViews.map((v) => ({ key: v.view_id, label: v.name })),
            savedViews.length > 0 ? { type: "divider" as const } : null,
            { key: "__save__", icon: <SaveOutlined />, label: "Save current view…" },
          ].filter((i): i is NonNullable<typeof i> => i !== null),
          onClick: ({ key }) => {
            if (key === "__save__") saveCurrentView();
            else { const v = savedViews.find((x) => x.view_id === key); if (v) applyView(v); }
          },
        }}>
          <Button>Saved Views</Button>
        </Dropdown>
        <Button type="primary" icon={<PlusOutlined />}
          onClick={() => { setEditingDef(null); setInitialTemplateId(null); setWizardOpen(true); }}>
          New Report
        </Button>
      </Flex>

      <Row gutter={[16, 16]} className="mb-4">
        <Col xs={24} sm={12} lg={8} xl={4}>
          <StatTile icon={<FileTextOutlined />} tint="green" value={String(stats?.total_reports ?? 0)}
            label="Total Reports"
            sub={stats && stats.total_delta_this_month > 0 ? `↑ ${stats.total_delta_this_month} this month` : undefined}
            subTone="up" />
        </Col>
        <Col xs={24} sm={12} lg={8} xl={4}>
          <StatTile icon={<CalendarOutlined />} tint="blue" value={String(stats?.scheduled_reports ?? 0)}
            label="Scheduled Reports"
            sub={stats?.next_schedule ? `Next: ${stats.next_schedule.name} – ${FREQ_LABEL[stats.next_schedule.frequency]}` : "None scheduled"} />
        </Col>
        <Col xs={24} sm={12} lg={8} xl={4}>
          <StatTile icon={<TeamOutlined />} tint="purple" value={String(stats?.shared_reports ?? 0)}
            label="Shared Reports" sub="With teams & individuals" />
        </Col>
        <Col xs={24} sm={12} lg={8} xl={4}>
          <StatTile icon={<DownloadOutlined />} tint="amber" value={String(stats?.total_downloads ?? 0)}
            label="Total Downloads" sub="All-time" />
        </Col>
        <Col xs={24} sm={12} lg={8} xl={4}>
          <StatTile icon={<CheckCircleOutlined />} tint="teal" value={`${stats?.delivery_success_pct ?? 100}%`}
            label="Delivery Success" sub="Last 30 days" />
        </Col>
      </Row>

      <Row gutter={16}>
        <Col xs={24} xl={18}>
          <Card size="small" bordered={false}>
            <Flex justify="space-between" align="center" wrap gap={8} className="mb-2">
              <Tabs
                activeKey={tab}
                onChange={(k) => setTab(k as ReportTab | "templates")}
                items={[
                  ...TAB_ITEMS,
                  { key: "templates", label: "Templates" },
                  { key: "archived", label: "Archived" },
                  { key: "confidential", label: <Badge count={0} size="small">Confidential</Badge> },
                ]}
                className="flex-1 min-w-0"
              />
              {tab !== "templates" && (
                <Flex gap={8} align="center">
                  <Select value={sort} onChange={setSort} size="small" className="w-40" options={[
                    { value: "recent", label: "Sort by: Newest" }, { value: "name", label: "Sort by: Name" },
                    { value: "last_run", label: "Sort by: Last Run" }, { value: "downloads", label: "Sort by: Downloads" },
                  ]} />
                  <Segmented size="small" value={view} onChange={(v) => setView(v as "list" | "grid")}
                    options={[{ value: "list", icon: <UnorderedListOutlined /> }, { value: "grid", icon: <TableOutlined /> }]} />
                </Flex>
              )}
            </Flex>

            {tab === "templates" ? (
              <Row gutter={[12, 12]}>
                {templates.map((t) => (
                  <Col key={t.template_id} xs={24} sm={12} lg={8}>
                    <Card size="small" className="h-full">
                      <Flex vertical gap={6}>
                        <Flex justify="space-between" align="center">
                          <Tag color={DOMAIN_CHIP[t.domain]} className="capitalize">{t.domain}</Tag>
                          <Tag color={TYPE_CHIP[t.type]} className="capitalize">{t.type}</Tag>
                        </Flex>
                        <Text strong className="text-[13px]">{t.name}</Text>
                        <Text type="secondary" className="text-[12px]">{t.description}</Text>
                        <Button size="small" type="primary" className="mt-1"
                          onClick={() => { setEditingDef(null); setInitialTemplateId(t.template_id); setWizardOpen(true); }}>
                          Use Template
                        </Button>
                      </Flex>
                    </Card>
                  </Col>
                ))}
              </Row>
            ) : defs === null ? (
              <Flex justify="center" className="pt-16"><Spin /></Flex>
            ) : visibleDefs.length === 0 ? (
              <Empty description="No reports match your filters." />
            ) : view === "list" ? (
              <Table
                size="small" rowKey="report_id" dataSource={visibleDefs} columns={columns}
                pagination={{ pageSize: 10, showTotal: (t, r) => `Showing ${r[0]} to ${r[1]} of ${t} reports` }}
                scroll={{ x: true }}
              />
            ) : (
              <>
                <Row gutter={[12, 12]}>
                  {paged.map((rd) => (
                    <Col key={rd.report_id} xs={24} sm={12} md={8} xl={6}>
                      <Card size="small" className="h-full cursor-pointer" onClick={() => setViewingDef(rd)}>
                        <Flex vertical gap={6}>
                          <Flex justify="space-between">
                            <Tag color={DOMAIN_CHIP[rd.domain]} className="capitalize">{rd.domain}</Tag>
                            <Tag color={TYPE_CHIP[rd.type]} className="capitalize">{rd.type}</Tag>
                          </Flex>
                          <Text strong className="text-[13px]" ellipsis>{rd.name}</Text>
                          <Text type="secondary" className="text-[11px]">{rd.is_mine ? "Me" : rd.owner_name}</Text>
                        </Flex>
                      </Card>
                    </Col>
                  ))}
                </Row>
                <Flex justify="end" className="mt-4">
                  <Pagination current={gridPage} pageSize={GRID_PAGE_SIZE} total={visibleDefs.length}
                    onChange={setGridPage} showTotal={(t, r) => `Showing ${r[0]} to ${r[1]} of ${t} reports`} />
                </Flex>
              </>
            )}
          </Card>
        </Col>

        <Col xs={24} xl={6}>
          <Card size="small" bordered={false} title="Quick Actions" className="mb-4">
            <Flex vertical gap={10}>
              <Flex align="center" gap={10} className="cursor-pointer"
                onClick={() => { setEditingDef(null); setInitialTemplateId(null); setWizardOpen(true); }}>
                <PlusOutlined className="text-io-600" />
                <div>
                  <Text strong className="text-[13px] block">Create Report</Text>
                  <Text type="secondary" className="text-[11px]">Build a new report from scratch</Text>
                </div>
              </Flex>
              {user?.role === "super_admin" && (
                <Flex align="center" gap={10} className="cursor-pointer" onClick={async () => {
                  try {
                    await api.syncIntegration("aws");
                    message.success("AWS data refreshed");
                    refreshAll();
                  } catch (e) {
                    message.error(e instanceof ApiError ? e.message : "Sync failed");
                  }
                }}>
                  <CloudUploadOutlined className="text-io-600" />
                  <div>
                    <Text strong className="text-[13px] block">Upload Data Source</Text>
                    <Text type="secondary" className="text-[11px]">Refresh AWS cost & usage data</Text>
                  </div>
                </Flex>
              )}
              <Flex align="center" gap={10} className="cursor-pointer" onClick={() => setTab("scheduled")}>
                <CalendarOutlined className="text-io-600" />
                <div>
                  <Text strong className="text-[13px] block">Manage Schedules</Text>
                  <Text type="secondary" className="text-[11px]">{pendingCount} active schedule(s)</Text>
                </div>
              </Flex>
              <Flex align="center" gap={10} className="cursor-pointer" onClick={() => setTab("templates")}>
                <FileProtectOutlined className="text-io-600" />
                <div>
                  <Text strong className="text-[13px] block">Report Templates</Text>
                  <Text type="secondary" className="text-[11px]">Use pre-built report templates</Text>
                </div>
              </Flex>
            </Flex>
          </Card>

          <RecentlyScheduled onOpenAll={() => setTab("scheduled")} />
        </Col>
      </Row>

      <ReportWizard
        open={wizardOpen} onClose={() => setWizardOpen(false)} meta={meta} templates={templates}
        editingDef={editingDef} initialTemplateId={initialTemplateId} canSchedule={canSchedule}
        canConfidential={canConfidential}
        onSaved={(saved, scheduleNow) => { refreshAll(); if (scheduleNow) setScheduleDef(saved); }}
      />
      <ReportViewer
        open={!!viewingDef} onClose={() => setViewingDef(null)} reportDef={viewingDef} level={level}
        onChanged={refreshAll}
      />
      <ScheduleModal
        open={!!scheduleDef} onClose={() => setScheduleDef(null)} reportDef={scheduleDef}
        onSaved={refreshAll}
      />
      <Modal
        title={`Share "${shareDef?.name ?? ""}"`} open={!!shareDef} onCancel={() => setShareDef(null)}
        onOk={() => shareForm.submit()} confirmLoading={sharing} okText="Share"
      >
        <Form form={shareForm} layout="vertical" onFinish={doShare}>
          <Form.Item name="user_ids" label="Share with" rules={[{ required: true, message: "Select at least one person" }]}>
            <Select mode="multiple" showSearch optionFilterProp="label"
              options={people.map((p) => ({ value: p.user_id, label: p.designation ? `${p.name} — ${p.designation}` : p.name }))} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

function RecentlyScheduled({ onOpenAll }: { onOpenAll: () => void }) {
  const [rows, setRows] = useState<ReportDef[] | null>(null);
  useEffect(() => {
    api.scheduledReports().then(setRows).catch(() => setRows([]));
  }, []);
  return (
    <Card size="small" bordered={false} title="Recently Scheduled">
      {rows === null ? (
        <Flex justify="center"><Spin size="small" /></Flex>
      ) : rows.length === 0 ? (
        <Text type="secondary" className="text-xs">No active schedules yet.</Text>
      ) : (
        <Flex vertical gap={10} className="mb-2">
          {rows.slice(0, 3).map((rd) => (
            <div key={rd.report_id}>
              <Text className="text-[13px] block" ellipsis>{rd.name}</Text>
              <Text type="secondary" className="text-[11px]">
                {FREQ_LABEL[rd.schedule?.frequency ?? "custom"]} at {rd.schedule?.time} UTC
              </Text>
            </div>
          ))}
        </Flex>
      )}
      <Button type="link" size="small" className="px-0" onClick={onOpenAll}>
        View all scheduled reports →
      </Button>
    </Card>
  );
}
