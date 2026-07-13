import { useCallback, useEffect, useState } from "react";
import {
  Button,
  Card,
  DatePicker,
  Dropdown,
  Empty,
  Flex,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Col,
  Select,
  Spin,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import {
  BankOutlined,
  CheckCircleOutlined,
  FileTextOutlined,
  MoreOutlined,
  PlusOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import { api, ApiError, type InvoiceStatus, type ProjectBilling, type ProjectInvoice } from "../../lib/api";
import { useAsyncAction } from "../../lib/useAsyncAction";
import StatTile from "../StatTile";

const { Text } = Typography;

const STATUS_TAG: Record<InvoiceStatus, string> = { paid: "success", pending: "processing", overdue: "error" };

function fmtMoney(n: number, currency: string): string {
  return `${currency} ${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

export default function BillingTab({ projectId }: { projectId: string }) {
  const [billing, setBilling] = useState<ProjectBilling | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<ProjectInvoice | null>(null);
  const [form] = Form.useForm();
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(() => {
    api.projectBilling(projectId).then(setBilling)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load billing"));
  }, [projectId]);

  useEffect(load, [load]);

  const [runSave, saving] = useAsyncAction(async (values: {
    number: string; date: dayjs.Dayjs; due_date?: dayjs.Dayjs | null;
    amount: number; status: InvoiceStatus; description?: string;
  }) => {
    const body = {
      number: values.number, date: values.date.format("YYYY-MM-DD"),
      due_date: values.due_date ? values.due_date.format("YYYY-MM-DD") : null,
      amount: values.amount, status: values.status, description: values.description ?? "",
    };
    try {
      if (editing) await api.updateInvoice(projectId, editing.invoice_id, body);
      else await api.createInvoice(projectId, body);
      message.success(editing ? "Invoice updated" : "Invoice added");
      setModalOpen(false);
      form.resetFields();
      load();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Save failed");
    }
  });

  async function markPaid(inv: ProjectInvoice) {
    setBusyId(inv.invoice_id);
    try {
      await api.updateInvoice(projectId, inv.invoice_id, { status: "paid" });
      message.success("Marked as paid");
      load();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Update failed");
    } finally {
      setBusyId(null);
    }
  }

  function openAdd() {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ status: "pending" });
    setModalOpen(true);
  }
  function openEdit(inv: ProjectInvoice) {
    setEditing(inv);
    form.setFieldsValue({
      number: inv.number, date: dayjs(inv.date),
      due_date: inv.due_date ? dayjs(inv.due_date) : null,
      amount: inv.amount, status: inv.status, description: inv.description,
    });
    setModalOpen(true);
  }

  if (error) return <Text type="danger">{error}</Text>;
  if (!billing) return <Flex justify="center" className="pt-16"><Spin /></Flex>;

  const currency = billing.currency;

  const columns = [
    { title: "Number", dataIndex: "number", key: "number", width: 160 },
    { title: "Date", dataIndex: "date", key: "date", width: 110 },
    { title: "Due", dataIndex: "due_date", key: "due_date", width: 110,
      render: (d?: string | null) => d ?? "—" },
    { title: "Description", dataIndex: "description", key: "description", ellipsis: true,
      render: (d?: string) => d || "—" },
    { title: "Amount", key: "amount", width: 130,
      render: (_: unknown, inv: ProjectInvoice) => fmtMoney(inv.amount, inv.currency) },
    {
      title: "Status", key: "status", width: 100,
      render: (_: unknown, inv: ProjectInvoice) => (
        <Tag color={STATUS_TAG[inv.status]} className="capitalize">{inv.status}</Tag>
      ),
    },
    {
      title: "", key: "actions", width: 50,
      render: (_: unknown, inv: ProjectInvoice) => (
        <Dropdown
          disabled={busyId === inv.invoice_id}
          menu={{
            items: [
              { key: "edit", label: "Edit" },
              { key: "paid", label: "Mark Paid", disabled: inv.status === "paid" },
            ],
            onClick: ({ key }) => {
              if (key === "edit") openEdit(inv);
              else if (key === "paid") markPaid(inv);
            },
          }}
        >
          <Button size="small" type="text" icon={<MoreOutlined />} loading={busyId === inv.invoice_id} />
        </Dropdown>
      ),
    },
  ];

  return (
    <div>
      <Row gutter={[12, 12]} className="mb-4">
        <Col xs={12} md={6}>
          <StatTile icon={<BankOutlined />} tint="indigo" label="Contract Value"
            value={billing.contract_value != null ? fmtMoney(billing.contract_value, currency) : "—"} />
        </Col>
        <Col xs={12} md={6}>
          <StatTile icon={<FileTextOutlined />} tint="blue" label="Invoiced"
            value={fmtMoney(billing.invoiced, currency)} />
        </Col>
        <Col xs={12} md={6}>
          <StatTile icon={<CheckCircleOutlined />} tint="green" label="Paid"
            value={fmtMoney(billing.paid, currency)} />
        </Col>
        <Col xs={12} md={6}>
          <StatTile icon={<WarningOutlined />} tint="amber" label="Outstanding"
            value={fmtMoney(billing.outstanding, currency)} />
        </Col>
      </Row>

      <Card
        size="small"
        title={`Invoices (${billing.invoices.length})`}
        extra={<Button type="primary" size="small" icon={<PlusOutlined />} onClick={openAdd}>Add Invoice</Button>}
      >
        {billing.invoices.length === 0 ? (
          <Empty description="No invoices yet — prospect." />
        ) : (
          <Table
            size="small" rowKey="invoice_id" dataSource={billing.invoices} columns={columns}
            pagination={{ pageSize: 10, showSizeChanger: false }} scroll={{ x: true }}
          />
        )}
      </Card>

      <Modal
        title={editing ? "Edit Invoice" : "Add Invoice"}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={saving}
        okText={editing ? "Save" : "Add"}
      >
        <Form form={form} layout="vertical" onFinish={runSave}>
          <Form.Item name="number" label="Invoice Number" rules={[{ required: true, message: "Required" }]}>
            <Input maxLength={60} />
          </Form.Item>
          <Flex gap={12}>
            <Form.Item name="date" label="Date" className="flex-1" rules={[{ required: true, message: "Required" }]}>
              <DatePicker className="w-full" />
            </Form.Item>
            <Form.Item name="due_date" label="Due Date" className="flex-1">
              <DatePicker className="w-full" />
            </Form.Item>
          </Flex>
          <Flex gap={12}>
            <Form.Item name="amount" label="Amount" className="flex-1" rules={[{ required: true, message: "Required" }]}>
              <InputNumber min={0} className="w-full" />
            </Form.Item>
            <Form.Item name="status" label="Status" className="flex-1" initialValue="pending">
              <Select options={[
                { value: "paid", label: "Paid" },
                { value: "pending", label: "Pending" },
                { value: "overdue", label: "Overdue" },
              ]} />
            </Form.Item>
          </Flex>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={2} maxLength={300} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
