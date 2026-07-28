import { useState } from "react";
import { Button, Dropdown, Modal, Table, Tooltip, Typography, App } from "antd";
import type { TableProps } from "antd";
import { DeleteOutlined, EditOutlined, EyeOutlined, MoreOutlined } from "@ant-design/icons";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError, type MilestoneRow } from "../../lib/api";
import { DueCell, HealthBadge, PriorityTag, ProgressCell, StatusTag } from "./MilestoneBadges";

const { Text } = Typography;

/** Server-paged milestone table. `onChanged` refetches the page after a
 * delete so the total and the pagination stay truthful. */
export default function MilestoneTable({
  rows,
  total,
  page,
  pageSize,
  loading,
  canManage,
  onPageChange,
  onSortChange,
  onEdit,
  onChanged,
}: {
  rows: MilestoneRow[];
  total: number;
  page: number;
  pageSize: number;
  loading?: boolean;
  canManage?: boolean;
  onPageChange: (page: number, pageSize: number) => void;
  onSortChange?: (sort: string, order: "asc" | "desc") => void;
  onEdit?: (row: MilestoneRow) => void;
  onChanged?: () => void;
}) {
  const navigate = useNavigate();
  const { message } = App.useApp();
  // Keyed by milestone so one row's spinner never freezes the whole table.
  const [busy, setBusy] = useState<Record<string, boolean>>({});

  const remove = (row: MilestoneRow) => {
    Modal.confirm({
      title: `Delete ${row.milestone_id}?`,
      content: `"${row.name}" and its tasks, daily entries and comments will be removed.`,
      okText: "Delete",
      okButtonProps: { danger: true },
      // antd shows a spinner on OK for as long as this promise is pending.
      onOk: async () => {
        setBusy((b) => ({ ...b, [row.milestone_id]: true }));
        try {
          await api.deleteMilestone(row.milestone_id);
          message.success(`${row.milestone_id} deleted`);
          onChanged?.();
        } catch (err) {
          message.error(err instanceof ApiError ? err.message : "Delete failed");
          throw err;
        } finally {
          setBusy((b) => ({ ...b, [row.milestone_id]: false }));
        }
      },
    });
  };

  const onChange: TableProps<MilestoneRow>["onChange"] = (_pagination, _filters, sorter) => {
    if (!onSortChange || Array.isArray(sorter) || !sorter?.field) return;
    onSortChange(String(sorter.field), sorter.order === "descend" ? "desc" : "asc");
  };

  return (
    <Table<MilestoneRow>
      rowKey="milestone_id"
      size="small"
      loading={loading}
      dataSource={rows ?? []}
      onChange={onChange}
      scroll={{ x: "max-content" }}
      pagination={{
        current: page,
        pageSize,
        total,
        showSizeChanger: true,
        pageSizeOptions: [10, 20, 50, 100],
        showTotal: (t, range) => `Showing ${range[0]} to ${range[1]} of ${t} milestones`,
        onChange: onPageChange,
      }}
      columns={[
        {
          title: "ID",
          dataIndex: "milestone_id",
          width: 110,
          sorter: true,
          render: (id: string) => (
            <Link to={`/milestones/detail/${id}`} className="whitespace-nowrap font-medium">
              {id}
            </Link>
          ),
        },
        {
          title: "Milestone Name",
          dataIndex: "name",
          sorter: true,
          render: (name: string, row) => (
            <div className="min-w-[180px]">
              <Link to={`/milestones/detail/${row.milestone_id}`}>{name}</Link>
              <div>
                <Text type="secondary" className="text-[11px]">
                  {row.category}
                </Text>
              </div>
            </div>
          ),
        },
        { title: "Project", dataIndex: "project_name", responsive: ["lg"] },
        { title: "Owner", dataIndex: "owner_name", responsive: ["md"] },
        { title: "Department", dataIndex: "department_name", responsive: ["xl"] },
        {
          title: "Status",
          dataIndex: "status",
          width: 140,
          sorter: true,
          render: (status: MilestoneRow["status"]) => <StatusTag status={status} />,
        },
        {
          title: "Progress",
          dataIndex: "progress_pct",
          width: 160,
          sorter: true,
          render: (value: number, row) => <ProgressCell value={value} status={row.status} />,
        },
        {
          title: "Priority",
          dataIndex: "priority",
          width: 100,
          sorter: true,
          responsive: ["lg"],
          render: (p: string) => <PriorityTag priority={p} />,
        },
        {
          title: "Due Date",
          dataIndex: "due_date",
          width: 130,
          sorter: true,
          render: (due: string, row) => (
            <DueCell due={due} overdue={row.overdue} overdueDays={row.overdue_days} />
          ),
        },
        {
          title: "Health",
          dataIndex: "health",
          width: 150,
          sorter: true,
          render: (_: unknown, row) => (
            <HealthBadge health={row.health} actual={row.actual_pct} planned={row.planned_pct} />
          ),
        },
        {
          title: "Actions",
          key: "actions",
          width: 110,
          fixed: "right",
          render: (_: unknown, row) => (
            <div className="flex items-center gap-1">
              <Tooltip title="View details">
                <Button
                  type="text"
                  size="small"
                  icon={<EyeOutlined />}
                  onClick={() => navigate(`/milestones/detail/${row.milestone_id}`)}
                />
              </Tooltip>
              {canManage && (
                <Tooltip title="Edit">
                  <Button
                    type="text"
                    size="small"
                    icon={<EditOutlined />}
                    onClick={() => onEdit?.(row)}
                  />
                </Tooltip>
              )}
              {canManage && (
                <Dropdown
                  disabled={busy[row.milestone_id]}
                  menu={{
                    items: [
                      {
                        key: "delete",
                        danger: true,
                        icon: <DeleteOutlined />,
                        label: "Delete milestone",
                        onClick: () => remove(row),
                      },
                    ],
                  }}
                >
                  <Button
                    type="text"
                    size="small"
                    icon={<MoreOutlined />}
                    loading={busy[row.milestone_id]}
                  />
                </Dropdown>
              )}
            </div>
          ),
        },
      ]}
    />
  );
}
