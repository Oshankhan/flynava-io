import { useEffect, useState } from "react";
import { Alert, Form, Input, Modal, Select, Steps, Switch, message } from "antd";
import {
  api, ApiError,
  type ReportDef, type ReportDomain, type ReportMeta, type ReportSectionSpec,
  type ReportTemplate, type ReportType, type ReportVisibility,
} from "../../lib/api";
import { useAsyncAction } from "../../lib/useAsyncAction";

const DOMAIN_LABEL: Record<ReportDomain, string> = {
  development: "Development", qa: "QA", operations: "Operations", projects: "Projects",
  marketing: "Marketing", sales: "Sales", finance: "Finance", hr: "HR",
  infrastructure: "Infrastructure",
};
const TYPE_LABEL: Record<ReportType, string> = {
  tabular: "Tabular", chart: "Chart", summary: "Summary", dashboard: "Dashboard",
};

function kindLabel(kind: string): string {
  return kind.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function ReportWizard({
  open, onClose, meta, templates, editingDef, initialTemplateId, canSchedule, canConfidential, onSaved,
}: {
  open: boolean;
  onClose: () => void;
  meta: ReportMeta | null;
  templates: ReportTemplate[];
  editingDef?: ReportDef | null;
  initialTemplateId?: string | null;
  canSchedule: boolean;
  canConfidential: boolean;
  onSaved: (def: ReportDef, scheduleNow: boolean) => void;
}) {
  const [form] = Form.useForm();
  const [step, setStep] = useState(0);
  const visibility: ReportVisibility | undefined = Form.useWatch("visibility", form);
  const confidential: boolean | undefined = Form.useWatch("confidential", form);
  const [templateSections, setTemplateSections] = useState<ReportSectionSpec[]>([]);
  const isEdit = !!editingDef;
  const steps = isEdit
    ? ["Basics", "Data Source", "Access & Recipients"]
    : ["Basics", "Data Source", "Access & Recipients", "Schedule"];

  useEffect(() => {
    if (!open) return;
    setStep(0);
    if (editingDef) {
      setTemplateSections(editingDef.sections);
      form.setFieldsValue({
        name: editingDef.name, description: editingDef.description, domain: editingDef.domain,
        project_id: editingDef.project_id ?? undefined, type: editingDef.type,
        sectionKinds: editingDef.sections.map((s) => s.kind),
        visibility: editingDef.visibility, roles: editingDef.access.roles,
        teams: editingDef.access.teams, confidential: editingDef.confidential,
        allowed_user_ids: editingDef.allowed_user_ids, recipients: editingDef.recipients,
      });
    } else {
      setTemplateSections([]);
      form.resetFields();
      form.setFieldsValue({ type: "tabular", visibility: "private", confidential: false, scheduleNow: false });
      if (initialTemplateId) applyTemplate(initialTemplateId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, editingDef, initialTemplateId, form]);

  function applyTemplate(templateId: string) {
    const tpl = templates.find((t) => t.template_id === templateId);
    if (!tpl) return;
    setTemplateSections(tpl.sections);
    form.setFieldsValue({
      name: form.getFieldValue("name") || tpl.name,
      description: form.getFieldValue("description") || tpl.description,
      domain: tpl.domain, type: tpl.type,
      sectionKinds: tpl.sections.map((s) => s.kind),
    });
  }

  const [save, saving] = useAsyncAction(async () => {
    try {
      const values = await form.validateFields();
      const sections: ReportSectionSpec[] = (values.sectionKinds as string[]).map((kind) => {
        const fromTemplate = templateSections.find((s) => s.kind === kind);
        return fromTemplate ?? { kind, params: {} };
      });
      const body = {
        name: values.name as string, description: (values.description as string) ?? "",
        domain: values.domain as ReportDomain, project_id: (values.project_id as string) || null,
        type: values.type as ReportType, sections,
        visibility: values.visibility as ReportVisibility,
        access: { roles: (values.roles as string[]) ?? [], teams: (values.teams as string[]) ?? [] },
        confidential: !!values.confidential,
        allowed_user_ids: (values.allowed_user_ids as string[]) ?? [],
        recipients: (values.recipients as string[]) ?? [],
      };
      const saved = editingDef
        ? await api.updateReportDef(editingDef.report_id, body)
        : await api.createReportDef(body);
      message.success(editingDef ? "Report updated" : "Report created");
      onSaved(saved, !editingDef && !!values.scheduleNow);
      onClose();
    } catch (e) {
      if (e instanceof ApiError) message.error(e.message);
      else if (e && typeof e === "object" && "errorFields" in e) return; // form validation — inline errors shown
      else message.error("Save failed");
    }
  });

  const sectionOptions = (meta?.section_kinds ?? []).map((k) => ({
    value: k.kind, label: kindLabel(k.kind) + (k.confidential ? " (confidential)" : ""),
  }));

  return (
    <Modal
      title={isEdit ? `Edit "${editingDef?.name}"` : "New Report"}
      open={open}
      width={640}
      okText={step === steps.length - 1 ? (isEdit ? "Save" : "Create") : "Next"}
      confirmLoading={saving}
      onOk={async () => {
        if (step < steps.length - 1) {
          try {
            await form.validateFields(step === 0 ? ["name", "domain", "type"] : undefined);
            setStep((s) => s + 1);
          } catch {
            // validation errors are shown inline by antd — stay on this step
          }
          return;
        }
        save();
      }}
      cancelText={step > 0 ? "Back" : "Cancel"}
      onCancel={() => (step > 0 ? setStep((s) => s - 1) : onClose())}
    >
      <Steps current={step} size="small" items={steps.map((s) => ({ title: s }))} className="mb-5" />
      <Form form={form} layout="vertical" preserve>
        <div className={step === 0 ? "" : "hidden"}>
          <Form.Item name="name" label="Report name" rules={[{ required: true, message: "Required" }]}>
            <Input placeholder="e.g. Weekly Campaign Performance" maxLength={200} />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={2} maxLength={500} />
          </Form.Item>
          <Form.Item name="domain" label="Domain" rules={[{ required: true, message: "Required" }]}>
            <Select options={(meta?.domains ?? []).map((d) => ({ value: d, label: DOMAIN_LABEL[d] ?? d }))} />
          </Form.Item>
          <Form.Item name="project_id" label="Project (optional)">
            <Select allowClear placeholder="No project"
              options={(meta?.projects ?? []).map((p) => ({ value: p.project_id, label: `${p.name} (${p.code})` }))} />
          </Form.Item>
          <Form.Item name="type" label="Report type" rules={[{ required: true, message: "Required" }]}>
            <Select options={(meta?.types ?? []).map((t) => ({ value: t, label: TYPE_LABEL[t] ?? t }))} />
          </Form.Item>
        </div>

        <div className={step === 1 ? "" : "hidden"}>
          <Form.Item label="Start from a template (optional)">
            <Select allowClear placeholder="Choose a template to prefill sections" onChange={applyTemplate}
              options={templates.map((t) => ({ value: t.template_id, label: t.name }))} />
          </Form.Item>
          <Form.Item name="sectionKinds" label="Sections" rules={[{ required: true, message: "Pick at least one section" }]}
            extra="Each section pulls one kind of data into the report.">
            <Select mode="multiple" options={sectionOptions} placeholder="Choose data sections" />
          </Form.Item>
        </div>

        <div className={step === 2 ? "" : "hidden"}>
          <Form.Item name="visibility" label="Who can see this report" rules={[{ required: true }]}>
            <Select
              disabled={!canSchedule}
              options={[
                { value: "private", label: "Private — only me" },
                { value: "restricted", label: "Restricted — specific roles/teams" },
                { value: "org", label: "Org — everyone" },
              ]}
            />
          </Form.Item>
          {!canSchedule && (
            <Alert type="info" showIcon className="mb-3"
              message="Your level only allows private reports. Ask a manager to widen access if needed." />
          )}
          {visibility === "restricted" && (
            <>
              <Form.Item name="roles" label="Visible to roles">
                <Select mode="tags" placeholder="e.g. manager, marketing" />
              </Form.Item>
              <Form.Item name="teams" label="Visible to teams">
                <Select mode="tags" placeholder="e.g. team_marketing" />
              </Form.Item>
            </>
          )}
          <Form.Item name="confidential" label="Confidential" valuePropName="checked"
            extra="Restricted to CEO tier and an explicit allowlist, regardless of the visibility above.">
            <Switch disabled={!canConfidential} />
          </Form.Item>
          {confidential && (
            <Form.Item name="allowed_user_ids" label="Additionally allow">
              <Select mode="multiple" showSearch optionFilterProp="label" placeholder="Select people"
                options={(meta?.users ?? []).map((u) => ({ value: u.user_id, label: u.name }))} />
            </Form.Item>
          )}
          <Form.Item name="recipients" label="Default recipients" extra="Used when sending or scheduling this report.">
            <Select mode="tags" placeholder="e.g. name@flynava.ai" tokenSeparators={[",", " "]} />
          </Form.Item>
        </div>

        {!isEdit && (
          <div className={step === 3 ? "" : "hidden"}>
            <Form.Item name="scheduleNow" label="Set up a recurring schedule" valuePropName="checked"
              extra="You'll be prompted to pick a frequency right after this report is created.">
              <Switch disabled={!canSchedule} />
            </Form.Item>
            {!canSchedule && (
              <Alert type="info" showIcon message="Scheduling requires L2+ (team lead or above)." />
            )}
          </div>
        )}
      </Form>
    </Modal>
  );
}
