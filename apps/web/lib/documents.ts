export type DocStatus = "draft" | "review" | "published";

export type DocTag =
  | "news"
  | "sop"
  | "best_practice"
  | "knowledge_base"
  | "faq";

export type DocSummary = {
  id: string;
  tenant_id: string;
  title: string;
  tag: string;
  status: DocStatus;
  version: string;
  create_at: string;
  update_at: string;
};

export type DocFile = {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  version: string;
  create_at: string;
  update_at: string;
};

export type DocDetail = DocSummary & {
  files: DocFile[];
};

export type IndexJobStatus = {
  status: "pending" | "running" | "succeeded" | "failed";
  error?: string | null;
  attempt_count: number;
  create_at: string;
  update_at: string;
};

export const TAG_OPTIONS: {
  value: DocTag;
  label: string;
  description: string;
}[] = [
  { value: "news", label: "公告动态", description: "通知、新闻、版本更新" },
  { value: "sop", label: "标准操作规程", description: "必须按步骤执行的流程" },
  {
    value: "best_practice",
    label: "最佳实践",
    description: "经验总结与推荐做法",
  },
  { value: "knowledge_base", label: "知识库", description: "通用参考文档" },
  { value: "faq", label: "常见问题", description: "问答式说明" },
];

export const TAG_TABS: { value: DocTag | "all"; label: string }[] = [
  { value: "all", label: "全部" },
  ...TAG_OPTIONS.map((o) => ({ value: o.value, label: o.label })),
];

export const STATUS_LABELS: Record<DocStatus, string> = {
  draft: "草稿",
  review: "待发布",
  published: "已发布",
};

export const ALLOWED_EXTENSIONS = [
  ".txt",
  ".md",
  ".pdf",
  ".doc",
  ".docx",
  ".ppt",
  ".pptx",
];

export const MAX_FILE_BYTES = 20 * 1024 * 1024;

export function tagLabel(tag: string): string {
  return TAG_OPTIONS.find((o) => o.value === tag)?.label ?? tag;
}

export function isAllowedFile(name: string): boolean {
  const lower = name.toLowerCase();
  return ALLOWED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}
