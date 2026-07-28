import { useEffect, useState } from "react";
import { Alert, Card, Flex, Input, List, Spin, Typography } from "antd";
import { Link } from "react-router-dom";
import { api, ApiError, type MilestoneFilterOption } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import EmployeeMilestones from "./EmployeeMilestones";

const { Text } = Typography;

/** Picker in front of screen 4. The owner list comes back already scoped, so
 * someone who can only see their own milestones gets a one-entry list — and
 * is shown their own screen directly rather than a pointless picker. */
export default function EmployeesTab() {
  const { user } = useAuth();
  const [owners, setOwners] = useState<MilestoneFilterOption[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [term, setTerm] = useState("");

  useEffect(() => {
    let alive = true;
    api
      .milestoneFilterOptions()
      .then((o) => alive && setOwners(o.owners ?? []))
      .catch((err) => alive && setError(err instanceof ApiError ? err.message : "Load failed"));
    return () => {
      alive = false;
    };
  }, []);

  if (error) return <Alert type="error" showIcon message="Cannot load employees" description={error} />;
  if (!owners)
    return (
      <Flex align="center" justify="center" className="min-h-[240px]">
        <Spin size="large" />
      </Flex>
    );

  const onlySelf = owners.length <= 1 && owners[0]?.value === user?.user_id;
  if (onlySelf || owners.length === 0) return <EmployeeMilestones userId={user?.user_id} />;

  const filtered = owners.filter((o) =>
    o.label?.toLowerCase().includes(term.trim().toLowerCase())
  );

  return (
    <Flex vertical gap={16}>
      <Card size="small" bordered={false} className="shadow-sm">
        <Input.Search
          placeholder="Find an employee"
          allowClear
          onChange={(e) => setTerm(e.target.value)}
        />
      </Card>
      <Card size="small" bordered={false} title={`Employees (${filtered.length})`}>
        <List
          size="small"
          grid={{ gutter: 12, xs: 1, sm: 2, lg: 3, xxl: 4 }}
          dataSource={filtered}
          renderItem={(owner) => (
            <List.Item>
              <Link to={`/milestones/employee/${owner.value}`}>
                <Card size="small" hoverable className="h-full">
                  <div className="font-medium truncate">{owner.label}</div>
                  <Text type="secondary" className="text-[11px]">
                    View milestones
                  </Text>
                </Card>
              </Link>
            </List.Item>
          )}
        />
      </Card>
    </Flex>
  );
}
