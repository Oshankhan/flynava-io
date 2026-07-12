import { useEffect, useState } from "react";
import {
  Card,
  Col,
  Descriptions,
  Empty,
  Flex,
  Row,
  Select,
  Statistic,
  Table,
  Tag,
  Typography,
} from "antd";
import { api, type EmployeeDetail, type Payslip } from "../lib/api";

const { Title, Text } = Typography;
const inr = (n: number) => `₹${n.toLocaleString("en-IN")}`;

export default function MyPayslip() {
  const [me, setMe] = useState<EmployeeDetail | null>(null);
  const [error, setError] = useState(false);
  const [month, setMonth] = useState<string>();

  useEffect(() => {
    api.hrMe().then((d) => {
      setMe(d);
      setMonth(d.payslips[0]?.month);
    }).catch(() => setError(true));
  }, []);

  if (error) return <Empty description="No employee record is linked to your account." />;
  if (!me) return <Card loading />;

  const slip: Payslip | undefined = me.payslips.find((p) => p.month === month) ?? me.payslips[0];

  return (
    <Flex vertical gap={16}>
      <Card>
        <Flex justify="space-between" wrap="wrap" gap={12}>
          <div>
            <Title level={4} className="m-0">{me.name}</Title>
            <Text type="secondary">
              {me.designation} · {me.department.toUpperCase()} · {me.emp_id}
            </Text>
            <div><Text type="secondary">{me.email} · joined {me.doj}</Text></div>
          </div>
          <Tag color={me.status === "active" ? "success" : "default"}>{me.status}</Tag>
        </Flex>
      </Card>

      <Row gutter={[16, 16]}>
        {Object.entries(me.leave_balance).map(([type, days]) => (
          <Col xs={8} key={type}>
            <Card size="small">
              <Statistic title={`${type} leave left`} value={days} suffix="days" />
            </Card>
          </Col>
        ))}
      </Row>

      <Card
        title="Payslip"
        extra={
          <Select
            size="small"
            value={month}
            className="w-[130px]"
            onChange={setMonth}
            options={me.payslips.map((p) => ({ value: p.month, label: p.month }))}
          />
        }
      >
        {slip && (
          <Descriptions bordered column={{ xs: 1, sm: 2, md: 3 }} size="small">
            <Descriptions.Item label="Month">{slip.month}</Descriptions.Item>
            <Descriptions.Item label="Gross">{inr(slip.gross)}</Descriptions.Item>
            <Descriptions.Item label="Basic">{inr(slip.basic)}</Descriptions.Item>
            <Descriptions.Item label="HRA">{inr(slip.hra)}</Descriptions.Item>
            <Descriptions.Item label="Allowances">{inr(slip.allowances)}</Descriptions.Item>
            <Descriptions.Item label="LOP days">{slip.lop_days}</Descriptions.Item>
            <Descriptions.Item label="PF">- {inr(slip.pf)}</Descriptions.Item>
            <Descriptions.Item label="Tax (TDS)">- {inr(slip.tax)}</Descriptions.Item>
            <Descriptions.Item label="Net Pay">
              <Text strong className="text-io-600">{inr(slip.net)}</Text>
            </Descriptions.Item>
          </Descriptions>
        )}
      </Card>

      <Card title="Leave History" size="small">
        <Table<EmployeeDetail["leaves"][number]>
          dataSource={me.leaves}
          rowKey="leave_id"
          size="small"
          pagination={false}
          scroll={{ x: true }}
          columns={[
            { title: "Type", dataIndex: "type", key: "type" },
            { title: "From", dataIndex: "from", key: "from" },
            { title: "To", dataIndex: "to", key: "to" },
            { title: "Days", dataIndex: "days", key: "days" },
            {
              title: "Status",
              dataIndex: "status",
              key: "status",
              render: (s: string) => (
                <Tag color={s === "Approved" ? "success" : "warning"}>{s}</Tag>
              ),
            },
          ]}
        />
      </Card>
    </Flex>
  );
}
