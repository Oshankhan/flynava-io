import { useCallback, useEffect, useState } from "react";
import { Avatar, Button, Card, Empty, Flex, List, Tag, Typography } from "antd";
import {
  AuditOutlined,
  BellOutlined,
  CalendarOutlined,
  CheckOutlined,
  ProfileOutlined,
} from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { api, type NotificationItem } from "../lib/api";
import { BRAND } from "../lib/brand";

const { Text } = Typography;

const TYPE_ICON: Record<string, React.ReactNode> = {
  approval_request: <AuditOutlined />,
  approval_decision: <AuditOutlined />,
  approval_update: <AuditOutlined />,
  meeting_invite: <CalendarOutlined />,
  meeting_cancelled: <CalendarOutlined />,
  task_assigned: <ProfileOutlined />,
};

export default function NotificationsPage() {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const navigate = useNavigate();

  const load = useCallback(() => {
    api.notifications().then(setItems).catch(() => setItems([]));
  }, []);

  useEffect(load, [load]);

  async function read(n: NotificationItem) {
    if (n.status === "unread") {
      await api.markRead(n.notif_id).catch(() => undefined);
      load();
    }
    if (n.action_link) navigate(n.action_link);
  }

  async function markAll() {
    await Promise.all(
      items.filter((n) => n.status === "unread").map((n) => api.markRead(n.notif_id))
    ).catch(() => undefined);
    load();
  }

  const unread = items.filter((n) => n.status === "unread").length;

  return (
    <div>
      <Flex justify="space-between" align="center" style={{ marginBottom: 12 }}>
        <Text type="secondary">
          {unread > 0 ? `${unread} unread` : "All caught up"}
        </Text>
        {unread > 0 && (
          <Button size="small" icon={<CheckOutlined />} onClick={markAll}>
            Mark all read
          </Button>
        )}
      </Flex>
      <Card size="small" bordered={false}>
        {items.length === 0 ? (
          <Empty description="No notifications yet" />
        ) : (
          <List
            dataSource={items}
            renderItem={(n) => (
              <List.Item
                onClick={() => read(n)}
                style={{ cursor: "pointer", opacity: n.status === "unread" ? 1 : 0.6 }}
                actions={[
                  n.status === "unread" ? (
                    <Tag key="s" color="processing">
                      new
                    </Tag>
                  ) : null,
                ]}
              >
                <List.Item.Meta
                  avatar={
                    <Avatar
                      style={{ background: n.status === "unread" ? BRAND.primary : "#9ca3af" }}
                      icon={TYPE_ICON[n.type] ?? <BellOutlined />}
                    />
                  }
                  title={
                    <Text strong={n.status === "unread"} style={{ fontSize: 14 }}>
                      {n.title}
                    </Text>
                  }
                  description={
                    <>
                      <Text style={{ fontSize: 12 }}>{n.body}</Text>
                      <div>
                        <Text type="secondary" style={{ fontSize: 11 }}>
                          {new Date(n.created_at).toLocaleString()}
                        </Text>
                      </div>
                    </>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Card>
    </div>
  );
}
