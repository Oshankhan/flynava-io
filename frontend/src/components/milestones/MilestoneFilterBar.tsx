import { useEffect, useState } from "react";
import { Button, Card, DatePicker, Input, Select } from "antd";
import { FilterOutlined, ReloadOutlined } from "@ant-design/icons";
import { api, type MilestoneFilterOptions, type MilestoneFilters } from "../../lib/api";
import { HEALTH_OPTIONS, STATUS_OPTIONS } from "./MilestoneBadges";

const { RangePicker } = DatePicker;

export type FilterField =
  | "department"
  | "team"
  | "project"
  | "category"
  | "manager"
  | "owner"
  | "status"
  | "priority"
  | "health"
  | "search"
  | "dates";

const ALL = "all";

/** Filter bar shared by the dashboard, the list and the department screen.
 * `fields` picks which controls to show, so each screen keeps only the ones
 * its API call actually honours. */
export default function MilestoneFilterBar({
  value,
  onChange,
  fields,
  loading,
  extra,
}: {
  value: MilestoneFilters;
  onChange: (next: MilestoneFilters) => void;
  fields: FilterField[];
  loading?: boolean;
  extra?: React.ReactNode;
}) {
  const [options, setOptions] = useState<MilestoneFilterOptions | null>(null);
  const [draft, setDraft] = useState<MilestoneFilters>(value);
  const [resetKey, setResetKey] = useState(0);

  useEffect(() => {
    let alive = true;
    api
      .milestoneFilterOptions()
      .then((o) => alive && setOptions(o))
      .catch(() => alive && setOptions(null));
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => setDraft(value), [value]);

  const has = (field: FilterField) => fields.includes(field);
  /** Dropdowns and the range picker only stage into `draft`; "Apply Filters"
   * commits. Firing a request per dropdown change would put five refetches
   * behind one user intent. The search box is the exception — pressing Enter
   * there IS the commit. */
  const set = (patch: MilestoneFilters, commit = false) => {
    const next = { ...draft, ...patch };
    setDraft(next);
    if (commit) onChange(next);
  };
  const pick = (key: keyof MilestoneFilters, v?: string) =>
    set({ [key]: v === ALL ? undefined : v } as MilestoneFilters);

  const selectProps = {
    allowClear: true,
    showSearch: true,
    optionFilterProp: "label" as const,
    className: "w-full",
    size: "middle" as const,
  };

  return (
    <Card size="small" bordered={false} className="shadow-sm">
      <div
        key={resetKey}
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3"
      >
        {has("search") && (
          <Input.Search
            placeholder="Search milestones"
            defaultValue={draft.q}
            allowClear
            onSearch={(v) => set({ q: v || undefined }, true)}
          />
        )}
        {has("department") && (
          <Select
            {...selectProps}
            placeholder="All Departments"
            value={draft.department ?? ALL}
            onChange={(v) => pick("department", v)}
            options={[{ value: ALL, label: "All Departments" }, ...(options?.departments ?? [])]}
          />
        )}
        {has("team") && (
          <Select
            {...selectProps}
            placeholder="All Teams"
            value={draft.team ?? ALL}
            onChange={(v) => pick("team", v)}
            options={[{ value: ALL, label: "All Teams" }, ...(options?.teams ?? [])]}
          />
        )}
        {has("project") && (
          <Select
            {...selectProps}
            placeholder="All Projects"
            value={draft.project ?? ALL}
            onChange={(v) => pick("project", v)}
            options={[{ value: ALL, label: "All Projects" }, ...(options?.projects ?? [])]}
          />
        )}
        {has("category") && (
          <Select
            {...selectProps}
            placeholder="All Categories"
            value={draft.category ?? ALL}
            onChange={(v) => pick("category", v)}
            options={[{ value: ALL, label: "All Categories" }, ...(options?.categories ?? [])]}
          />
        )}
        {has("manager") && (
          <Select
            {...selectProps}
            placeholder="All Managers"
            value={draft.manager ?? ALL}
            onChange={(v) => pick("manager", v)}
            options={[{ value: ALL, label: "All Managers" }, ...(options?.managers ?? [])]}
          />
        )}
        {has("owner") && (
          <Select
            {...selectProps}
            placeholder="All Owners"
            value={draft.owner ?? ALL}
            onChange={(v) => pick("owner", v)}
            options={[{ value: ALL, label: "All Owners" }, ...(options?.owners ?? [])]}
          />
        )}
        {has("status") && (
          <Select
            {...selectProps}
            placeholder="All Status"
            value={draft.status ?? ALL}
            onChange={(v) => pick("status", v)}
            options={[{ value: ALL, label: "All Status" }, ...STATUS_OPTIONS]}
          />
        )}
        {has("priority") && (
          <Select
            {...selectProps}
            placeholder="All Priority"
            value={draft.priority ?? ALL}
            onChange={(v) => pick("priority", v)}
            options={[
              { value: ALL, label: "All Priority" },
              ...(options?.priorities ?? ["High", "Medium", "Low"]).map((p) => ({
                value: p,
                label: p,
              })),
            ]}
          />
        )}
        {has("health") && (
          <Select
            {...selectProps}
            placeholder="All Health"
            value={draft.health ?? ALL}
            onChange={(v) => pick("health", v)}
            options={[{ value: ALL, label: "All Health" }, ...HEALTH_OPTIONS]}
          />
        )}
        {has("dates") && (
          <RangePicker
            className="w-full"
            onChange={(_, strings) =>
              set({
                date_from: strings?.[0] || undefined,
                date_to: strings?.[1] || undefined,
              })
            }
          />
        )}
      </div>
      <div className="flex flex-wrap items-center justify-end gap-2 mt-3">
        {extra}
        <Button
          icon={<ReloadOutlined />}
          // Reset commits an empty filter set, which refetches — so it has to
          // be blocked while a request is already in flight (see CLAUDE.md).
          disabled={loading}
          onClick={() => {
            // The search box and the range picker are uncontrolled (they hold
            // dayjs values antd owns), so remount them to clear the visible
            // state along with the query.
            setResetKey((k) => k + 1);
            setDraft({});
            onChange({});
          }}
        >
          Reset
        </Button>
        <Button
          type="primary"
          icon={<FilterOutlined />}
          loading={loading}
          onClick={() => onChange({ ...draft })}
        >
          Apply Filters
        </Button>
      </div>
    </Card>
  );
}
