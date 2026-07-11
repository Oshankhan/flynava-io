import { useEffect, useState } from "react";
import { Badge, Button, Empty, List, Popover, Typography } from "antd";
import { BellOutlined } from "@ant-design/icons";
import { api, type NotificationItem } from "../lib/api";

const { Text } = Typography;

export default function NotificationBell() {
  const [count, setCount] = useState(0);
  const [items, setItems] = useState<NotificationItem[]>([]);

  async function refresh() {
    try {
      setCount((await api.unreadCount()).count);
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 30000);
    return () => clearInterval(t);
  }, []);

  async function openChange(open: boolean) {
    if (open) setItems(await api.notifications());
  }

  async function read(id: string) {
    await api.markRead(id);
    setItems((xs) => xs.map((n) => (n.notif_id === id ? { ...n, status: "read" } : n)));
    refresh();
  }

  const content = (
    <div style={{ width: 320, maxHeight: 380, overflowY: "auto" }}>
      {items.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No notifications" />
      ) : (
        <List
          size="small"
          dataSource={items}
          renderItem={(n) => (
            <List.Item
              onClick={() => read(n.notif_id)}
              style={{ cursor: "pointer", opacity: n.status === "unread" ? 1 : 0.6 }}
            >
              <List.Item.Meta
                title={
                  <Text strong={n.status === "unread"} style={{ fontSize: 13 }}>
                    {n.title}
                  </Text>
                }
                description={<Text style={{ fontSize: 12 }}>{n.body}</Text>}
              />
            </List.Item>
          )}
        />
      )}
    </div>
  );

  return (
    <Popover content={content} trigger="click" onOpenChange={openChange} placement="bottomRight">
      <Badge count={count} size="small" data-testid="notif-badge">
        <Button type="text" shape="circle" icon={<BellOutlined />} aria-label="Notifications" />
      </Badge>
    </Popover>
  );
}
