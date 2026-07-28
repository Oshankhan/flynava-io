import { useState } from "react";
import {
  App,
  Button,
  Card,
  Empty,
  Form,
  Input,
  List,
  Select,
  Table,
  Timeline,
  Typography,
} from "antd";
import { FileOutlined, LinkOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import {
  api,
  ApiError,
  type MilestoneActivity,
  type MilestoneComment,
  type MilestoneDocument,
  type MilestoneRow,
} from "../../../lib/api";
import { HealthBadge, ProgressCell, StatusTag } from "../MilestoneBadges";

const { Text, Paragraph } = Typography;

export function DependenciesTab({
  milestoneId,
  dependencies,
  canManage,
  onChanged,
}: {
  milestoneId: string;
  dependencies: MilestoneRow[];
  canManage: boolean;
  onChanged: () => void | Promise<void>;
}) {
  const { message } = App.useApp();
  const [options, setOptions] = useState<{ value: string; label: string }[]>([]);
  const [selected, setSelected] = useState<string[]>(
    (dependencies ?? []).map((d) => d.milestone_id)
  );
  const [saving, setSaving] = useState(false);
  const [searching, setSearching] = useState(false);

  const search = async (term: string) => {
    if (!term) return;
    setSearching(true);
    try {
      const page = await api.milestoneList({ q: term }, { page_size: 20 });
      setOptions(
        page.items
          .filter((m) => m.milestone_id !== milestoneId)
          .map((m) => ({ value: m.milestone_id, label: `${m.milestone_id} — ${m.name}` }))
      );
    } catch {
      setOptions([]);
    } finally {
      setSearching(false);
    }
  };

  const save = async () => {
    setSaving(true);
    try {
      await api.setMilestoneDependencies(milestoneId, selected);
      message.success("Dependencies updated");
      await onChanged();
    } catch (err) {
      message.error(err instanceof ApiError ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card size="small" bordered={false} title="Dependencies">
      {canManage && (
        <div className="flex flex-col sm:flex-row gap-2 mb-4">
          <Select
            mode="multiple"
            className="flex-1"
            placeholder="Search milestones this one depends on"
            value={selected}
            onChange={setSelected}
            onSearch={search}
            filterOption={false}
            loading={searching}
            options={[
              ...options,
              ...(dependencies ?? []).map((d) => ({
                value: d.milestone_id,
                label: `${d.milestone_id} — ${d.name}`,
              })),
            ]}
          />
          <Button type="primary" loading={saving} onClick={save}>
            Save
          </Button>
        </div>
      )}
      <Table<MilestoneRow>
        rowKey="milestone_id"
        size="small"
        dataSource={dependencies ?? []}
        pagination={false}
        scroll={{ x: "max-content" }}
        locale={{ emptyText: "This milestone has no dependencies." }}
        columns={[
          {
            title: "ID",
            dataIndex: "milestone_id",
            width: 110,
            render: (id: string) => <Link to={`/milestones/detail/${id}`}>{id}</Link>,
          },
          { title: "Milestone", dataIndex: "name" },
          { title: "Owner", dataIndex: "owner_name", responsive: ["md"] },
          {
            title: "Status",
            dataIndex: "status",
            width: 140,
            render: (s: MilestoneRow["status"]) => <StatusTag status={s} />,
          },
          {
            title: "Progress",
            dataIndex: "progress_pct",
            width: 160,
            render: (v: number, row) => <ProgressCell value={v} status={row.status} />,
          },
          { title: "Due", dataIndex: "due_date", width: 120 },
          {
            title: "Health",
            key: "health",
            width: 150,
            render: (_: unknown, row) => (
              <HealthBadge health={row.health} actual={row.actual_pct} planned={row.planned_pct} />
            ),
          },
        ]}
      />
    </Card>
  );
}

export function DocumentsTab({
  milestoneId,
  documents,
  canManage,
  onChanged,
}: {
  milestoneId: string;
  documents: MilestoneDocument[];
  canManage: boolean;
  onChanged: () => void | Promise<void>;
}) {
  const { message } = App.useApp();
  const [form] = Form.useForm<{ name: string; url?: string }>();
  const [saving, setSaving] = useState(false);

  const link = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      await api.linkMilestoneDocument(milestoneId, values);
      message.success("Document linked");
      form.resetFields();
      await onChanged();
    } catch (err) {
      message.error(err instanceof ApiError ? err.message : "Could not link document");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card size="small" bordered={false} title="Documents">
      {canManage && (
        <Form form={form} layout="inline" className="mb-4 gap-2" disabled={saving}>
          <Form.Item name="name" rules={[{ required: true, message: "Name required" }]} className="flex-1 min-w-[180px]">
            <Input placeholder="Document name" />
          </Form.Item>
          <Form.Item name="url" className="flex-1 min-w-[180px]">
            <Input placeholder="https://…" />
          </Form.Item>
          <Button type="primary" icon={<LinkOutlined />} loading={saving} onClick={link}>
            Link
          </Button>
        </Form>
      )}
      {documents?.length ? (
        <List
          size="small"
          dataSource={documents}
          renderItem={(doc) => (
            <List.Item>
              <List.Item.Meta
                avatar={<FileOutlined />}
                title={
                  doc.url ? (
                    <a href={doc.url} target="_blank" rel="noreferrer">
                      {doc.name}
                    </a>
                  ) : (
                    doc.name
                  )
                }
                description={
                  <Text type="secondary" className="text-[11px]">
                    {doc.kind ?? "link"} · {doc.uploaded_at?.slice(0, 10) ?? ""}
                  </Text>
                }
              />
            </List.Item>
          )}
        />
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No documents linked" />
      )}
    </Card>
  );
}

export function TimelineTab({ events }: { events: MilestoneActivity[] }) {
  if (!events?.length)
    return (
      <Card size="small" bordered={false} title="Timeline">
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Nothing recorded yet" />
      </Card>
    );
  return (
    <Card size="small" bordered={false} title="Timeline">
      <Timeline
        items={events.map((e) => ({
          key: e.event_id,
          color: e.type.includes("rejected") ? "red" : e.type.includes("completed") ? "green" : "blue",
          children: (
            <div>
              <Text strong className="capitalize">
                {e.type.replace(/_/g, " ")}
              </Text>
              {e.detail && <div className="text-sm">{e.detail}</div>}
              <Text type="secondary" className="text-[11px]">
                {e.actor_name ?? e.actor_id} · {new Date(e.at).toLocaleString()}
              </Text>
            </div>
          ),
        }))}
      />
    </Card>
  );
}

export function CommentsTab({
  milestoneId,
  comments,
  onChanged,
}: {
  milestoneId: string;
  comments: MilestoneComment[];
  onChanged: () => void | Promise<void>;
}) {
  const { message } = App.useApp();
  const [body, setBody] = useState("");
  const [saving, setSaving] = useState(false);

  const post = async () => {
    if (!body.trim()) return;
    setSaving(true);
    try {
      await api.addMilestoneComment(milestoneId, body.trim());
      setBody("");
      await onChanged();
    } catch (err) {
      message.error(err instanceof ApiError ? err.message : "Could not post comment");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card size="small" bordered={false} title="Comments">
      {comments?.length ? (
        <List
          size="small"
          dataSource={comments}
          renderItem={(c) => (
            <List.Item key={c.comment_id}>
              <div className="w-full">
                <Text strong>{c.user_name ?? c.user_id}</Text>{" "}
                <Text type="secondary" className="text-[11px]">
                  {new Date(c.created_at).toLocaleString()}
                </Text>
                <Paragraph className="!mb-0">{c.body}</Paragraph>
              </div>
            </List.Item>
          )}
        />
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No comments yet" />
      )}
      <div className="flex flex-col sm:flex-row gap-2 mt-3">
        <Input.TextArea
          rows={2}
          value={body}
          disabled={saving}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Add a comment"
        />
        <Button type="primary" loading={saving} disabled={!body.trim()} onClick={post}>
          Post
        </Button>
      </div>
    </Card>
  );
}
