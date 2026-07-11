import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, Button, Card, Flex, Form, Input, Typography } from "antd";
import { LockOutlined, MailOutlined } from "@ant-design/icons";
import { ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { BRAND } from "../lib/brand";

const { Title, Text } = Typography;

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onFinish(values: { email: string; password: string }) {
    setBusy(true);
    setError(null);
    try {
      await login(values.email, values.password);
      navigate("/workspace", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Flex
      align="center"
      justify="center"
      style={{
        minHeight: "100vh",
        background: `linear-gradient(135deg, ${BRAND.primary} 0%, ${BRAND.primaryStrong} 100%)`,
        padding: 16,
      }}
    >
      <Card style={{ width: 380, boxShadow: "0 12px 40px rgba(0,0,0,0.25)" }}>
        <Flex align="center" gap={12} style={{ marginBottom: 20 }}>
          <img
            src="/flynava-logo.png"
            alt="FlyNava Technologies"
            style={{ height: 44, width: "auto" }}
          />
          <div>
            <Title level={4} style={{ margin: 0, color: BRAND.primary }}>
              IO
            </Title>
            <Text type="secondary">FlyNava Technologies</Text>
          </div>
        </Flex>

        <Form name="login" layout="vertical" onFinish={onFinish} requiredMark={false}>
          <Form.Item
            label="Email"
            name="email"
            rules={[{ required: true, type: "email", message: "Enter a valid email" }]}
          >
            <Input prefix={<MailOutlined />} placeholder="you@flynava.ai" size="large" />
          </Form.Item>
          <Form.Item
            label="Password"
            name="password"
            rules={[{ required: true, message: "Enter your password" }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="••••••••" size="large" />
          </Form.Item>
          {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 12 }} />}
          <Button type="primary" htmlType="submit" size="large" block loading={busy}>
            Sign in
          </Button>
        </Form>
      </Card>
    </Flex>
  );
}
