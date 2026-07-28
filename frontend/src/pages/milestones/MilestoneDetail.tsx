import { useCallback, useEffect, useState } from "react";
import { Alert, Breadcrumb, Button, Flex, Spin, Tabs, Typography } from "antd";
import { EditOutlined, ReloadOutlined } from "@ant-design/icons";
import { Link, useParams } from "react-router-dom";
import { api, ApiError, type MilestoneDetailPayload } from "../../lib/api";
import { useAsyncAction } from "../../lib/useAsyncAction";
import OverviewTab from "../../components/milestones/detail/OverviewTab";
import TasksTab from "../../components/milestones/detail/TasksTab";
import DailySuccessTab from "../../components/milestones/detail/DailySuccessTab";
import {
  CommentsTab,
  DependenciesTab,
  DocumentsTab,
  TimelineTab,
} from "../../components/milestones/detail/SideTabs";
import MilestoneFormModal from "../../components/milestones/MilestoneFormModal";
import { StatusTag } from "../../components/milestones/MilestoneBadges";

const { Text, Title } = Typography;

export default function MilestoneDetail() {
  const { milestoneId = "" } = useParams();
  const [data, setData] = useState<MilestoneDetailPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await api.milestoneDetail(milestoneId));
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Load failed");
    }
  }, [milestoneId]);

  useEffect(() => {
    load();
  }, [load]);

  const [refresh, refreshing] = useAsyncAction(load);

  if (error)
    return <Alert type="error" showIcon message="Cannot load milestone" description={error} />;
  if (!data)
    return (
      <Flex align="center" justify="center" className="min-h-[240px]">
        <Spin size="large" />
      </Flex>
    );

  const m = data.milestone;
  const canManage = !!data.permissions?.can_manage;

  return (
    <Flex vertical gap={16}>
      <Breadcrumb
        items={[
          { title: <Link to="/milestones/dashboard">Milestone Tracker</Link> },
          { title: <Link to="/milestones/list">Milestone List</Link> },
          { title: m.milestone_id },
        ]}
      />

      <Flex justify="space-between" align="center" wrap gap={8}>
        <div className="min-w-0">
          <Title level={4} className="!mb-0 truncate">
            {m.name}
          </Title>
          <Flex align="center" gap={8} wrap>
            <StatusTag status={m.status} />
            <Text type="secondary" className="text-xs">
              {m.milestone_id} · {m.project_name ?? "No project"} · owner {m.owner_name ?? "—"}
            </Text>
          </Flex>
        </div>
        <Flex gap={8}>
          {canManage && (
            <Button icon={<EditOutlined />} onClick={() => setEditing(true)}>
              Edit
            </Button>
          )}
          <Button icon={<ReloadOutlined />} loading={refreshing} onClick={refresh}>
            Refresh
          </Button>
        </Flex>
      </Flex>

      <Tabs
        defaultActiveKey="overview"
        items={[
          { key: "overview", label: "Overview", children: <OverviewTab data={data} /> },
          {
            key: "tasks",
            label: `Tasks (${data.counts?.tasks ?? 0})`,
            children: (
              <TasksTab
                milestoneId={milestoneId}
                tasks={data.tasks}
                canManage={canManage}
                onChanged={load}
              />
            ),
          },
          {
            key: "daily",
            label: `Daily Success (${data.counts?.daily_entries ?? 0})`,
            children: (
              <DailySuccessTab
                milestoneId={milestoneId}
                entries={data.daily_entries}
                tasks={data.tasks}
                canApprove={!!data.permissions?.can_approve}
                onChanged={load}
              />
            ),
          },
          {
            key: "dependencies",
            label: `Dependencies (${data.counts?.dependencies ?? 0})`,
            children: (
              <DependenciesTab
                milestoneId={milestoneId}
                dependencies={data.dependencies}
                canManage={canManage}
                onChanged={load}
              />
            ),
          },
          {
            key: "documents",
            label: `Documents (${data.counts?.documents ?? 0})`,
            children: (
              <DocumentsTab
                milestoneId={milestoneId}
                documents={data.documents}
                canManage={canManage}
                onChanged={load}
              />
            ),
          },
          { key: "timeline", label: "Timeline", children: <TimelineTab events={data.timeline} /> },
          {
            key: "comments",
            label: `Comments (${data.counts?.comments ?? 0})`,
            children: (
              <CommentsTab milestoneId={milestoneId} comments={data.comments} onChanged={load} />
            ),
          },
        ]}
      />

      <MilestoneFormModal
        open={editing}
        milestone={m}
        onClose={() => setEditing(false)}
        onSaved={load}
      />
    </Flex>
  );
}
