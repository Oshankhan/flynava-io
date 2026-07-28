import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Flex } from "antd";
import { DownloadOutlined, PlusOutlined } from "@ant-design/icons";
import { api, ApiError, type MilestoneFilters, type MilestoneRow } from "../../lib/api";
import { useAsyncAction } from "../../lib/useAsyncAction";
import { useAuth } from "../../lib/auth";
import { levelOf } from "../../lib/rbac";
import MilestoneFilterBar from "../../components/milestones/MilestoneFilterBar";
import MilestoneTable from "../../components/milestones/MilestoneTable";
import MilestoneFormModal from "../../components/milestones/MilestoneFormModal";

export default function ListTab() {
  const { user } = useAuth();
  // Mirrors the backend's `can_manage`: team leads and above, or the owner of
  // the individual row (the table re-checks per row for the latter).
  const canManage = levelOf(user) >= 2;

  const [filters, setFilters] = useState<MilestoneFilters>({});
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [sort, setSort] = useState<{ sort: string; order: "asc" | "desc" }>({
    sort: "due_date",
    order: "asc",
  });
  const [rows, setRows] = useState<MilestoneRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<MilestoneRow | null>(null);
  const [formOpen, setFormOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.milestoneList(filters, { page, page_size: pageSize, ...sort });
      setRows(data.items ?? []);
      setTotal(data.total ?? 0);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Load failed");
    } finally {
      setLoading(false);
    }
  }, [filters, page, pageSize, sort]);

  useEffect(() => {
    load();
  }, [load]);

  const [exportCsv, exporting] = useAsyncAction(() => api.exportMilestones(filters));

  if (error)
    return <Alert type="error" showIcon message="Cannot load milestones" description={error} />;

  return (
    <Flex vertical gap={16}>
      <MilestoneFilterBar
        value={filters}
        loading={loading}
        onChange={(next) => {
          setPage(1);
          setFilters(next);
        }}
        fields={["search", "department", "status", "priority", "owner", "health", "dates"]}
        extra={
          <>
            {canManage && (
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => {
                  setEditing(null);
                  setFormOpen(true);
                }}
              >
                Create Milestone
              </Button>
            )}
            <Button icon={<DownloadOutlined />} loading={exporting} onClick={exportCsv}>
              Export
            </Button>
          </>
        }
      />

      <MilestoneTable
        rows={rows}
        total={total}
        page={page}
        pageSize={pageSize}
        loading={loading}
        canManage={canManage}
        onPageChange={(nextPage, nextSize) => {
          setPage(nextPage);
          setPageSize(nextSize);
        }}
        onSortChange={(field, order) => setSort({ sort: field, order })}
        onEdit={(row) => {
          setEditing(row);
          setFormOpen(true);
        }}
        onChanged={load}
      />

      <MilestoneFormModal
        open={formOpen}
        milestone={editing}
        onClose={() => setFormOpen(false)}
        onSaved={load}
      />
    </Flex>
  );
}
