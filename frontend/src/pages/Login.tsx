import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, Button, Card, Flex, Form, Input, Typography } from "antd";
import { LockOutlined, MailOutlined } from "@ant-design/icons";
import { ApiError } from "../lib/api";
import { SESSION_EXPIRED_KEY, useAuth } from "../lib/auth";

const { Title, Text } = Typography;

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sessionExpired] = useState(() => {
    const expired = localStorage.getItem(SESSION_EXPIRED_KEY) === "1";
    if (expired) localStorage.removeItem(SESSION_EXPIRED_KEY);
    return expired;
  });

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
      className="min-h-screen bg-gradient-to-br from-io-600 to-io-900 p-4"
    >
      <Card className="w-full max-w-[380px] shadow-2xl">
        <Flex align="center" gap={12} className="mb-5">
          <img
            src="/flynava-logo.png"
            alt="FlyNava Technologies"
            className="h-11 w-auto"
          />
          <div>
            <Title level={4} className="m-0 text-io-600">
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
          {sessionExpired && !error && (
            <Alert
              type="warning"
              message="Your session expired. Please sign in again."
              showIcon
              className="mb-3"
            />
          )}
          {error && <Alert type="error" message={error} showIcon className="mb-3" />}
          <Button type="primary" htmlType="submit" size="large" block loading={busy}>
            Sign in
          </Button>
        </Form>
      </Card>
    </Flex>
  );
}
