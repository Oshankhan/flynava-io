import { useEffect, useMemo, useState } from "react";
import { Alert, Card, Flex, Spin, Tree, Typography } from "antd";
import type { TreeDataNode } from "antd";
import { ApartmentOutlined, UserOutlined } from "@ant-design/icons";
import { api, ApiError, type UserLite } from "../lib/api";
import { BRAND } from "../lib/brand";

const { Text } = Typography;

function nodeTitle(u: UserLite): React.ReactNode {
  return (
    <Flex align="center" gap={8}>
      <UserOutlined style={{ color: BRAND.primary }} />
      <Text strong style={{ fontSize: 13 }}>{u.name}</Text>
      {u.designation && (
        <Text type="secondary" style={{ fontSize: 12 }}>— {u.designation}</Text>
      )}
      {u.team_id && (
        <Text type="secondary" style={{ fontSize: 11 }}>({u.team_id.replace("team_", "")})</Text>
      )}
    </Flex>
  );
}

function buildTree(users: UserLite[]): TreeDataNode[] {
  const byId = new Map(users.map((u) => [u.user_id, u]));
  const childrenOf = new Map<string, UserLite[]>();
  const roots: UserLite[] = [];

  for (const u of users) {
    const parent = u.reports_to;
    if (parent && byId.has(parent)) {
      if (!childrenOf.has(parent)) childrenOf.set(parent, []);
      childrenOf.get(parent)!.push(u);
    } else {
      roots.push(u);
    }
  }

  function toNode(u: UserLite): TreeDataNode {
    const kids = (childrenOf.get(u.user_id) ?? []).sort((a, b) => a.name.localeCompare(b.name));
    return {
      key: u.user_id,
      title: nodeTitle(u),
      children: kids.length > 0 ? kids.map(toNode) : undefined,
    };
  }

  // Highest level first (CEO/Founder at the top), then alphabetical.
  roots.sort((a, b) => (b.level ?? 0) - (a.level ?? 0) || a.name.localeCompare(b.name));
  return roots.map(toNode);
}

export default function OrgChart() {
  const [users, setUsers] = useState<UserLite[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .orgUsers()
      .then(setUsers)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load org chart"));
  }, []);

  const treeData = useMemo(() => (users ? buildTree(users) : []), [users]);
  const allKeys = useMemo(() => users?.map((u) => u.user_id) ?? [], [users]);

  if (error) return <Alert type="error" message={error} showIcon />;
  if (!users)
    return (
      <Flex justify="center" style={{ paddingTop: 80 }}>
        <Spin />
      </Flex>
    );

  return (
    <Card
      size="small"
      bordered={false}
      title={
        <Flex align="center" gap={6}>
          <ApartmentOutlined style={{ color: BRAND.primary }} /> Organization Chart
        </Flex>
      }
    >
      {treeData.length === 0 ? (
        <Text type="secondary">No users to show.</Text>
      ) : (
        <Tree
          showLine
          defaultExpandedKeys={allKeys}
          selectable={false}
          treeData={treeData}
        />
      )}
    </Card>
  );
}
