import { useEffect, useMemo, useState } from "react";
import { Card, Empty, Flex, Input, List, Spin, Tag, Typography, message } from "antd";
import { FilePdfOutlined, FileTextOutlined, SearchOutlined } from "@ant-design/icons";
import { api, ApiError, type IoDocument } from "../lib/api";

const { Text } = Typography;

const KIND_LABEL: Record<string, string> = {
  policy: "Policy",
  mom: "Minutes of Meeting",
  document: "Document",
};

export default function KnowledgeBase() {
  const [docs, setDocs] = useState<IoDocument[]>([]);
  const [q, setQ] = useState("");
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  useEffect(() => {
    api.documents().then(setDocs).catch(() => setDocs([]));
  }, []);

  // Knowledge base = the approved corpus (policies, MOMs, documents).
  const approved = useMemo(
    () =>
      docs
        .filter((d) => d.status === "approved")
        .filter((d) => !q || d.title.toLowerCase().includes(q.toLowerCase())),
    [docs, q]
  );

  async function download(d: IoDocument) {
    setDownloadingId(d.doc_id);
    try {
      await api.downloadDocument(d.doc_id, d.filename || d.title);
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Download failed");
    } finally {
      setDownloadingId(null);
    }
  }

  return (
    <div>
      <Flex justify="space-between" align="center" className="mb-3" wrap gap={8}>
        <Text type="secondary">
          Approved policies, meeting minutes and documents — searchable, always current.
        </Text>
        <Input
          prefix={<SearchOutlined />}
          placeholder="Search knowledge base…"
          allowClear
          className="max-w-[320px]"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </Flex>
      <Card size="small" bordered={false}>
        {approved.length === 0 ? (
          <Empty description="No approved documents yet — approved uploads appear here automatically." />
        ) : (
          <List
            dataSource={approved}
            renderItem={(d) => (
              <List.Item
                className="cursor-pointer"
                onClick={() => download(d)}
                actions={[<Tag key="k">{KIND_LABEL[d.kind] ?? d.kind}</Tag>]}
              >
                <List.Item.Meta
                  avatar={
                    downloadingId === d.doc_id ? (
                      <Spin size="small" />
                    ) : d.filename?.toLowerCase().endsWith(".pdf") ? (
                      <FilePdfOutlined className="text-[22px] text-red-600" />
                    ) : (
                      <FileTextOutlined className="text-[22px] text-io-600" />
                    )
                  }
                  title={<Text strong>{d.title}</Text>}
                  description={
                    <Text type="secondary" className="text-xs">
                      {d.filename} · {(d.size / 1024).toFixed(0)} KB ·{" "}
                      {new Date(d.created_at).toLocaleDateString()}
                    </Text>
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
