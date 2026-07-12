import { Tag } from "antd";
import type { Rag } from "../lib/api";
import { RAG } from "../lib/brand";

export default function RagBadge({ rag }: { rag: Rag }) {
  const meta = RAG[rag];
  return (
    <Tag color={meta.color} data-testid={`rag-${rag}`} className="me-0">
      {meta.label}
    </Tag>
  );
}
