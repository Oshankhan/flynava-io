import type { ReactNode } from "react";
import { Result } from "antd";
import { useAuth } from "../lib/auth";
import { levelOf } from "../lib/rbac";

interface Props {
  min: number;
  children: ReactNode;
}

export default function RequireLevel({ min, children }: Props) {
  const { user } = useAuth();
  if (levelOf(user) < min) {
    return (
      <Result
        status="403"
        title="403"
        subTitle="Department heads and above only."
      />
    );
  }
  return <>{children}</>;
}
