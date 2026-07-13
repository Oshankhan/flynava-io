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
  const [markingAll, setMarkingAll] = useState(false);
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
    setMarkingAll(true);
    try {
      await Promise.all(
        items.filter((n) => n.status === "unread").map((n) => api.markRead(n.notif_id))
      ).catch(() => undefined);
      load();
    } finally {
      setMarkingAll(false);
    }
  }

  const unread = items.filter((n) => n.status === "unread").length;

  return (
    <div>
      <Flex justify="space-between" align="center" className="mb-3">
        <Text type="secondary">
          {unread > 0 ? `${unread} unread` : "All caught up"}
        </Text>
        {unread > 0 && (
          <Button size="small" icon={<CheckOutlined />} loading={markingAll} onClick={markAll}>
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
                className={`cursor-pointer ${n.status === "unread" ? "opacity-100" : "opacity-60"}`}
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
                      className={n.status === "unread" ? "bg-io-600" : "bg-gray-400"}
                      icon={TYPE_ICON[n.type] ?? <BellOutlined />}
                    />
                  }
                  title={
                    <Text strong={n.status === "unread"} className="text-sm">
                      {n.title}
                    </Text>
                  }
                  description={
                    <>
                      <Text className="text-xs">{n.body}</Text>
                      <div>
                        <Text type="secondary" className="text-[11px]">
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
