import { useEffect, useState } from "react";
import { Button, Card, Col, Flex, List, Row, Table, Tag, Typography } from "antd";
import {
  AlertOutlined,
  ExperimentOutlined,
  FileSearchOutlined,
  FundOutlined,
  TeamOutlined,
  UserAddOutlined,
} from "@ant-design/icons";
import {
  api,
  type ComplianceItem,
  type KpiSeries,
  type MyTasks,
  type PendingLeave,
  type Position,
  type ProjectRow,
  type TeamTasks,
} from "../lib/api";
import ProjectHealth from "./ProjectHealth";
import TrendChart from "./TrendChart";

const { Text } = Typography;

type Variant = "l1" | "l2";

function isRetest(status: string | null | undefined): boolean {
  return /retest|in testing/i.test(status ?? "");
}

// --- Engineering (Java/Python dev teams): L2 gets a project-health glance ---
function EngPanel({ variant }: { variant: Variant }) {
  const [projects, setProjects] = useState<ProjectRow[] | null>(null);

  useEffect(() => {
    if (variant === "l2")
      api.getDashboard("manager").then((d) => setProjects(d.projects)).catch(() => setProjects([]));
  }, [variant]);

  if (variant !== "l2" || !projects || projects.length === 0) return null;
  return <ProjectHealth projects={projects} />;
}

// --- QA team: retest queue + bugs I reported (L1), team retest load (L2) ---
function QaPanel({ variant }: { variant: Variant }) {
  const [mine, setMine] = useState<MyTasks | null>(null);
  const [team, setTeam] = useState<TeamTasks | null>(null);

  useEffect(() => {
    if (variant === "l1") api.myTasks().then(setMine).catch(() => setMine(null));
    else api.teamTasks().then(setTeam).catch(() => setTeam(null));
  }, [variant]);

  if (variant === "l1") {
    if (!mine) return null;
    const retest = mine.rows.filter((t) => isRetest(t.status));
    const authored = mine.authored ?? [];
    if (retest.length === 0 && authored.length === 0) return null;
    return (
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card
            size="small"
            bordered={false}
            title={
              <Flex align="center" gap={6}>
                <ExperimentOutlined className="text-[#7cc8e0]" /> Retest Queue
              </Flex>
            }
          >
            {retest.length === 0 ? (
              <Text type="secondary" className="text-xs">Nothing to retest right now.</Text>
            ) : (
              <List
                size="small"
                dataSource={retest}
                renderItem={(t) => (
                  <List.Item
                    actions={[
                      <Tag key="p" color={/high|immediate/i.test(t.priority ?? "") ? "red" : undefined}>
                        {t.priority ?? "—"}
                      </Tag>,
                    ]}
                  >
                    <Text className="text-[13px]">{t.title}</Text>
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card
            size="small"
            bordered={false}
            title={
              <Flex align="center" gap={6}>
                <FileSearchOutlined className="text-io-600" /> Bugs I Reported
              </Flex>
            }
          >
            {authored.length === 0 ? (
              <Text type="secondary" className="text-xs">No bugs reported under your name.</Text>
            ) : (
              <List
                size="small"
                dataSource={authored}
                renderItem={(t) => (
                  <List.Item actions={[<Tag key="s">{t.status ?? "—"}</Tag>]}>
                    <Text className="text-[13px]">{t.title}</Text>
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>
      </Row>
    );
  }

  if (!team) return null;
  const withRetest = team.members.map((m) => ({
    ...m,
    retest: team.rows.filter((r) => r.assignee === m.name && isRetest(r.status)).length,
  }));
  if (withRetest.length === 0) return null;
  return (
    <Card
      size="small"
      bordered={false}
      title={
        <Flex align="center" gap={6}>
          <ExperimentOutlined className="text-[#7cc8e0]" /> Team Retest Workload
        </Flex>
      }
    >
      <Table
        size="small"
        rowKey="user_id"
        dataSource={withRetest}
        pagination={false}
        columns={[
          { title: "Member", dataIndex: "name", key: "name" },
          {
            title: "Awaiting Retest",
            dataIndex: "retest",
            key: "retest",
            width: 140,
            render: (v: number) => <Tag color={v > 0 ? "blue" : undefined}>{v}</Tag>,
          },
        ]}
      />
    </Card>
  );
}

// --- Finance: compliance deadlines (L1+L2), revenue/expense trend (L2) ---
function FinPanel({ variant }: { variant: Variant }) {
  const [items, setItems] = useState<ComplianceItem[]>([]);
  const [revenue, setRevenue] = useState<KpiSeries | null>(null);
  const [expenses, setExpenses] = useState<KpiSeries | null>(null);

  useEffect(() => {
    api.complianceItems().then(setItems).catch(() => setItems([]));
    if (variant === "l2") {
      api.kpiHistory("fin_revenue_mtd").then(setRevenue).catch(() => setRevenue(null));
      api.kpiHistory("fin_expenses_mtd").then(setExpenses).catch(() => setExpenses(null));
    }
  }, [variant]);

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} lg={variant === "l2" ? 8 : 24}>
        <Card
          size="small"
          bordered={false}
          title={
            <Flex align="center" gap={6}>
              <AlertOutlined className="text-amber-500" /> Compliance Deadlines
            </Flex>
          }
        >
          {items.length === 0 ? (
            <Text type="secondary" className="text-xs">Nothing on the calendar.</Text>
          ) : (
            <List
              size="small"
              dataSource={items}
              renderItem={(c) => (
                <List.Item
                  actions={[
                    <Tag key="s" color={c.status === "overdue" ? "error" : "warning"}>{c.status}</Tag>,
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <Text className={`text-[13px] ${c.owner === "Finance" ? "font-semibold" : "font-normal"}`}>
                        {c.title}
                      </Text>
                    }
                    description={
                      <Text type="secondary" className="text-[11px]">
                        {c.owner} · due {c.due_date}
                      </Text>
                    }
                  />
                </List.Item>
              )}
            />
          )}
        </Card>
      </Col>
      {variant === "l2" && revenue && (
        <Col xs={24} lg={8}>
          <TrendChart series={revenue} />
        </Col>
      )}
      {variant === "l2" && expenses && (
        <Col xs={24} lg={8}>
          <TrendChart series={expenses} />
        </Col>
      )}
    </Row>
  );
}

// --- HR: open positions (recruiter, L1), pending leaves queue (HR TL, L2) ---
function HrPanel({ variant }: { variant: Variant }) {
  const [positions, setPositions] = useState<Position[]>([]);
  const [pending, setPending] = useState<PendingLeave[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = () => {
    if (variant === "l1") api.positions().then(setPositions).catch(() => setPositions([]));
    else api.pendingLeaves().then(setPending).catch(() => setPending([]));
  };

  useEffect(load, [variant]);

  async function act(id: string, action: "approve" | "reject") {
    setBusyId(id);
    try {
      await api.decideLeave(id, action).catch(() => undefined);
      load();
    } finally {
      setBusyId(null);
    }
  }

  if (variant === "l1") {
    if (positions.length === 0) return null;
    return (
      <Card
        size="small"
        bordered={false}
        title={
          <Flex align="center" gap={6}>
            <UserAddOutlined className="text-io-600" /> Open Positions
          </Flex>
        }
      >
        <Table
          size="small"
          rowKey="pos_id"
          dataSource={positions}
          pagination={false}
          columns={[
            { title: "Role", dataIndex: "title", key: "title" },
            { title: "Dept", dataIndex: "dept", key: "dept", width: 90 },
            {
              title: "Days Open",
              dataIndex: "days_open",
              key: "days_open",
              width: 110,
              render: (v: number) => <Tag color={v > 40 ? "red" : v > 20 ? "orange" : undefined}>{v}</Tag>,
            },
            { title: "Candidates", dataIndex: "candidates", key: "candidates", width: 100 },
          ]}
        />
      </Card>
    );
  }

  if (pending.length === 0) return null;
  return (
    <Card
      size="small"
      bordered={false}
      title={
        <Flex align="center" gap={6}>
          <TeamOutlined className="text-io-600" /> Pending Leaves ({pending.length})
        </Flex>
      }
    >
      <Table
        size="small"
        rowKey="leave_id"
        dataSource={pending}
        pagination={false}
        columns={[
          { title: "Employee", dataIndex: "emp_name", key: "emp_name" },
          { title: "Type", dataIndex: "type", key: "type", width: 90 },
          {
            title: "Dates",
            key: "dates",
            width: 220,
            render: (_: unknown, r: PendingLeave) => `${r.from} → ${r.to} · ${r.days}d`,
          },
          {
            title: "Actions",
            key: "actions",
            width: 170,
            render: (_: unknown, r: PendingLeave) => (
              <Flex gap={4}>
                <Button size="small" type="primary" loading={busyId === r.leave_id}
                  onClick={() => act(r.leave_id, "approve")}>
                  Approve
                </Button>
                <Button size="small" danger loading={busyId === r.leave_id}
                  onClick={() => act(r.leave_id, "reject")}>
                  Reject
                </Button>
              </Flex>
            ),
          },
        ]}
      />
    </Card>
  );
}

// --- Marketing: KPI mini-trend (L1), lead funnel (L2) ---
// Uses /kpis/{id}/history (department-scoped access) rather than the
// module-RBAC /kpis snapshot — that matrix gates marketing_sales behind a
// literal "marketing" role, which none of the seeded mkt team members hold.
function MktPanel({ variant }: { variant: Variant }) {
  const [leads, setLeads] = useState<KpiSeries | null>(null);
  const [sessions, setSessions] = useState<KpiSeries | null>(null);
  const [conversion, setConversion] = useState<KpiSeries | null>(null);
  const [pipeline, setPipeline] = useState<KpiSeries | null>(null);

  useEffect(() => {
    api.kpiHistory("mkt_leads").then(setLeads).catch(() => setLeads(null));
    if (variant === "l1") {
      api.kpiHistory("mkt_sessions").then(setSessions).catch(() => setSessions(null));
    } else {
      api.kpiHistory("mkt_conversion").then(setConversion).catch(() => setConversion(null));
      api.kpiHistory("mkt_pipeline").then(setPipeline).catch(() => setPipeline(null));
    }
  }, [variant]);

  if (variant === "l1") {
    if (!leads && !sessions) return null;
    return (
      <Row gutter={[16, 16]}>
        {leads && (
          <Col xs={24} md={12}>
            <TrendChart series={leads} />
          </Col>
        )}
        {sessions && (
          <Col xs={24} md={12}>
            <TrendChart series={sessions} />
          </Col>
        )}
      </Row>
    );
  }

  if (!leads && !conversion && !pipeline) return null;
  return (
    <Card
      size="small"
      bordered={false}
      title={
        <Flex align="center" gap={6}>
          <FundOutlined className="text-io-600" /> Lead Funnel
        </Flex>
      }
    >
      <Row gutter={[16, 16]}>
        {leads && (
          <Col xs={24} md={8}>
            <TrendChart series={leads} />
          </Col>
        )}
        {conversion && (
          <Col xs={24} md={8}>
            <TrendChart series={conversion} />
          </Col>
        )}
        {pipeline && (
          <Col xs={24} md={8}>
            <TrendChart series={pipeline} />
          </Col>
        )}
      </Row>
    </Card>
  );
}

export default function DeptPanel({
  department,
  teamId,
  variant,
}: {
  department?: string | null;
  teamId?: string | null;
  variant: Variant;
}) {
  if (department === "eng") {
    return teamId === "team_qa" ? <QaPanel variant={variant} /> : <EngPanel variant={variant} />;
  }
  if (department === "fin") return <FinPanel variant={variant} />;
  if (department === "hr") return <HrPanel variant={variant} />;
  if (department === "mkt") return <MktPanel variant={variant} />;
  return null;
}
