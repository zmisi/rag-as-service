import type { DocDetail, DocSummary, IngestJobStatus } from "./documents";

const API_PREFIX = "/backend";

export function backendUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${API_PREFIX}${normalized}`;
}

/** Rewrite API redirect URLs for local dev (http + :3000). Production keeps https. */
export function resolvePostRegistrationUrl(redirectUrl: string): string {
  if (typeof window === "undefined") {
    return redirectUrl;
  }

  let target: URL;
  try {
    target = new URL(redirectUrl);
  } catch {
    return redirectUrl;
  }

  const { protocol, hostname, port } = window.location;
  const onLocalApex =
    hostname === "lxzxai.com" || hostname.endsWith(".lxzxai.com");

  if (onLocalApex && port && port !== "443" && port !== "80") {
    target.protocol = protocol;
    target.port = port;
  }

  return target.toString();
}

/** Build main-site URL with local dev port when on *.lxzxai.com. */
export function resolveMainSiteUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  if (typeof window === "undefined") {
    return `https://lxzxai.com${normalized}`;
  }

  const { protocol, port } = window.location;
  let base = `${protocol}//lxzxai.com`;
  if (port && port !== "443" && port !== "80") {
    base += `:${port}`;
  }
  return `${base}${normalized}`;
}

export async function fetchBackend(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  return fetch(backendUrl(path), {
    ...init,
    credentials: "include",
  });
}

export type AuthMe = {
  user_id: string;
  email: string;
  tenant_id?: string | null;
  subdomain?: string | null;
  role?: "owner" | "admin" | "member" | null;
  must_change_password?: boolean;
};

export async function getAuthMe() {
  const response = await fetchBackend("/api/v1/auth/me", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`无法获取当前用户信息: ${response.status}`);
  }
  return (await response.json()) as AuthMe;
}

export type ConversationStatus = "active" | "archived";

export type Conversation = {
  id: string;
  tenant_id: string;
  user_id?: string | null;
  site_key_id?: string | null;
  title: string;
  status: ConversationStatus;
  create_at: string;
  update_at: string;
};

export type Message = {
  id: string;
  conversation_id: string;
  tenant_id: string;
  role: "user" | "assistant" | "system" | "tool" | "summary";
  content: string;
  meta?: Record<string, unknown> | null;
  agent_run_id?: string | null;
  create_at: string;
  update_at: string;
};

export type TurnReply = {
  user: Message;
  assistant: Message;
  agent_run_id: string;
  used_search: boolean;
  status: "completed" | "truncated" | "error";
  conversation_title?: string | null;
  conversation_id?: string | null;
};

export type FaqSuggestion = {
  document_group_id: string;
  document_id: string;
  question: string;
  click_count: number;
  hot: boolean;
};

export type FaqClickResult = {
  document_group_id: string;
  document_id: string;
  question: string;
  click_count: number;
  hot: boolean;
};

type StreamEvent =
  | { event: "started"; data: { conversation_id: string } }
  | { event: "progress"; data: { stage: string; elapsed_ms: number } }
  | { event: "done"; data: TurnReply & { server_ms?: number } }
  | { event: "error"; data: { message: string } };

type PostMessageStreamOptions = {
  onStarted?: (conversationId: string) => void;
  onProgress?: (stage: string, elapsedMs: number) => void;
};

function authHeaders(): HeadersInit {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const userId = process.env.NEXT_PUBLIC_DEV_USER_ID;
  if (userId) {
    headers["X-Test-User-Id"] = userId;
  }
  return headers;
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? "GET").toUpperCase();
  const t0 = performance.now();
  const res = await fetch(`/backend/v1${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...authHeaders(),
      ...(init?.headers ?? {}),
    },
  });
  const networkMs = performance.now() - t0;
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* ignore */
    }
    console.info(
      `[timing] api ${method} ${path} status=${res.status} network_ms=${networkMs.toFixed(1)} error=${detail}`,
    );
    throw new Error(`${res.status}: ${detail}`);
  }
  if (res.status === 204) {
    console.info(
      `[timing] api ${method} ${path} status=204 network_ms=${networkMs.toFixed(1)}`,
    );
    return undefined as T;
  }
  const parseT0 = performance.now();
  const data = (await res.json()) as T;
  const parseMs = performance.now() - parseT0;
  const serverMs = res.headers.get("X-Turn-Duration-Ms");
  const serverTiming = res.headers.get("Server-Timing");
  console.info(
    `[timing] api ${method} ${path} status=${res.status} network_ms=${networkMs.toFixed(1)} parse_ms=${parseMs.toFixed(1)}` +
      (serverMs ? ` server_ms=${serverMs}` : "") +
      (serverTiming ? ` server_timing=${serverTiming}` : ""),
  );
  return data;
}

export function listConversations(status: ConversationStatus = "active") {
  return api<Conversation[]>(`/conversations?status=${status}`);
}

export function createConversation(title?: string) {
  return api<Conversation>("/conversations", {
    method: "POST",
    body: JSON.stringify(title ? { title } : {}),
  });
}

export function archiveConversation(id: string) {
  return api<Conversation>(`/conversations/${id}/archive`, { method: "POST" });
}

export function unarchiveConversation(id: string) {
  return api<Conversation>(`/conversations/${id}/unarchive`, {
    method: "POST",
  });
}

export function deleteConversation(id: string) {
  return api<void>(`/conversations/${id}`, { method: "DELETE" });
}

export function renameConversation(id: string, title: string) {
  return api<Conversation>(`/conversations/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}

export function listMessages(conversationId: string) {
  return api<Message[]>(`/conversations/${conversationId}/messages`);
}

export async function postMessage(conversationId: string, content: string) {
  const t0 = performance.now();
  console.info(
    `[timing] chat.send start conversation_id=${conversationId} content_chars=${content.length}`,
  );
  try {
    const turn = await api<TurnReply>(
      `/conversations/${conversationId}/messages`,
      {
        method: "POST",
        body: JSON.stringify({ role: "user", content }),
      },
    );
    console.info(
      `[timing] chat.send done conversation_id=${conversationId} ` +
        `client_total_ms=${(performance.now() - t0).toFixed(1)} ` +
        `status=${turn.status} used_search=${turn.used_search} ` +
        `agent_run_id=${turn.agent_run_id}`,
    );
    return turn;
  } catch (err) {
    console.info(
      `[timing] chat.send fail conversation_id=${conversationId} ` +
        `client_total_ms=${(performance.now() - t0).toFixed(1)} ` +
        `error=${err instanceof Error ? err.message : String(err)}`,
    );
    throw err;
  }
}

export async function postMessageStream(
  conversationId: string | null,
  content: string,
  options?: PostMessageStreamOptions,
): Promise<TurnReply> {
  const t0 = performance.now();
  /** F14: collection route when draft (null id); else legacy path-id stream. */
  const url = conversationId
    ? `/backend/v1/conversations/${conversationId}/messages/stream`
    : `/backend/v1/conversations/messages/stream`;
  const body = conversationId
    ? { role: "user", content }
    : { role: "user", content, conversation_id: null };
  const res = await fetch(url, {
    method: "POST",
    credentials: "include",
    headers: {
      ...authHeaders(),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) {
    let detail = res.statusText;
    try {
      const errBody = await res.json();
      if (typeof errBody?.detail === "string") detail = errBody.detail;
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status}: ${detail}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let doneTurn: TurnReply | null = null;
  let resolvedId = conversationId;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";
    for (const raw of chunks) {
      const parsed = parseSse(raw);
      if (!parsed) continue;
      if (parsed.event === "started") {
        resolvedId = parsed.data.conversation_id;
        options?.onStarted?.(parsed.data.conversation_id);
      } else if (parsed.event === "progress") {
        options?.onProgress?.(parsed.data.stage, parsed.data.elapsed_ms);
      } else if (parsed.event === "done") {
        doneTurn = parsed.data;
      } else if (parsed.event === "error") {
        throw new Error(parsed.data.message || "streaming failed");
      }
    }
  }

  if (!doneTurn) {
    throw new Error("stream finished without done event");
  }
  if (!doneTurn.conversation_id && resolvedId) {
    doneTurn = { ...doneTurn, conversation_id: resolvedId };
  }
  console.info(
    `[timing] chat.stream done conversation_id=${doneTurn.conversation_id ?? resolvedId} ` +
      `client_total_ms=${(performance.now() - t0).toFixed(1)} ` +
      `status=${doneTurn.status} used_search=${doneTurn.used_search}`,
  );
  return doneTurn;
}

export function listFaqSuggestions(offset = 0) {
  return api<FaqSuggestion[]>(
    `/portal/faq-suggestions?offset=${encodeURIComponent(String(offset))}`,
  );
}

export function clickFaqSuggestion(documentGroupId: string) {
  return api<FaqClickResult>(
    `/portal/faq-suggestions/${documentGroupId}/click`,
    { method: "POST" },
  );
}

function parseSse(raw: string): StreamEvent | null {
  let event = "";
  const dataLines: string[] = [];
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trim());
    }
  }
  if (!event || dataLines.length === 0) return null;
  try {
    return { event, data: JSON.parse(dataLines.join("\n")) } as StreamEvent;
  } catch {
    return null;
  }
}

// --- F03 documents ---

function tenantHeaders(extra?: HeadersInit): HeadersInit {
  const headers: Record<string, string> = {};
  const userId = process.env.NEXT_PUBLIC_DEV_USER_ID;
  if (userId) {
    headers["X-Test-User-Id"] = userId;
  }
  return { ...headers, ...(extra as Record<string, string>) };
}

async function docApi<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/backend/v1${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...tenantHeaders(),
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") {
        detail = body.detail;
      } else if (body?.detail && typeof body.detail === "object") {
        const d = body.detail as {
          message?: string;
          existing_title?: string;
          existing_document_id?: string;
        };
        detail =
          d.message ||
          (d.existing_title
            ? `知识库中已存在相同内容的文档「${d.existing_title}」`
            : JSON.stringify(body.detail));
      }
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export function listDocuments(tag?: string) {
  const q = tag ? `?tag=${encodeURIComponent(tag)}` : "";
  return docApi<DocSummary[]>(`/documents${q}`);
}

export function getDocument(id: string) {
  return docApi<DocDetail>(`/documents/${id}`);
}

export function createDocument() {
  return docApi<DocSummary>("/documents", { method: "POST" });
}

export function saveDocument(
  id: string,
  body: { title?: string; tag?: string },
) {
  return docApi<DocDetail>(`/documents/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function deleteDocument(id: string) {
  return docApi<void>(`/documents/${id}`, { method: "DELETE" });
}

export async function downloadDocument(id: string, fallbackName = "download") {
  const res = await fetch(`/backend/v1/documents/${id}/download`, {
    method: "GET",
    credentials: "include",
    headers: tenantHeaders(),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail || "下载失败");
  }
  const blob = await res.blob();
  let filename = fallbackName;
  const cd = res.headers.get("Content-Disposition");
  if (cd) {
    const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(cd);
    const plain = /filename="?([^";]+)"?/i.exec(cd);
    if (utf8?.[1]) {
      try {
        filename = decodeURIComponent(utf8[1]);
      } catch {
        filename = utf8[1];
      }
    } else if (plain?.[1]) {
      filename = plain[1];
    }
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export type DocumentPreview = {
  blobUrl: string;
  contentType: string;
  kind: "pdf" | "html" | "text" | "other";
};

export async function fetchDocumentPreview(id: string): Promise<DocumentPreview> {
  const res = await fetch(`/backend/v1/documents/${id}/preview`, {
    method: "GET",
    credentials: "include",
    headers: tenantHeaders(),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail || "预览失败");
  }
  const contentType = (res.headers.get("Content-Type") || "").toLowerCase();
  const blob = await res.blob();
  const blobUrl = URL.createObjectURL(blob);
  let kind: DocumentPreview["kind"] = "other";
  if (contentType.includes("pdf")) kind = "pdf";
  else if (contentType.includes("html")) kind = "html";
  else if (contentType.includes("text")) kind = "text";
  return { blobUrl, contentType, kind };
}

export async function uploadDocumentFile(id: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  return docApi<DocDetail>(`/documents/${id}/files`, {
    method: "POST",
    body: form,
  });
}

export function submitForReview(
  id: string,
  body?: { reviewer_user_id?: string | null; review_comment?: string },
) {
  return docApi<DocDetail>(`/documents/${id}/submit-review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
}

export function publishDocument(
  id: string,
  body?: { review_comment?: string },
) {
  return docApi<DocDetail>(`/documents/${id}/publish`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
}

export function completeDocumentReview(
  id: string,
  body: { decision: "approve" | "reject"; review_comment?: string },
) {
  return docApi<DocDetail>(`/documents/${id}/complete-review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function newDocumentVersion(id: string) {
  return docApi<DocDetail>(`/documents/${id}/new-version`, { method: "POST" });
}

export function getIngestStatus(id: string) {
  return docApi<IngestJobStatus | null>(`/documents/${id}/ingest-status`);
}

/* ---- P2-F02 Folder tree (admin) ---- */

export type FolderVisibility = "public" | "partial" | "private";

export type FolderNode = {
  folder_id: string;
  parent_id: string | null;
  name: string;
  description?: string;
  visibility?: FolderVisibility;
};

export type FolderLayerDoc = {
  doc_id: string;
  doc_name: string;
  publish_status: string;
  ingest_status: string;
  status_label: string;
  folder_id: string | null;
  create_at: string | null;
  uploader?: string | null;
  reviewer?: string | null;
  reviewed_at?: string | null;
  review_comment?: string | null;
};

export type FolderLayer = {
  folder_id: string | null;
  breadcrumb: FolderNode[];
  folders: FolderNode[];
  documents: FolderLayerDoc[];
};

export type ReviewTask = FolderLayerDoc;

export type ReviewerOption = {
  user_id: string;
  name: string;
  email: string;
};

export function listFolderTree() {
  return api<FolderNode[]>("/folders/tree");
}

export function listFolderLayer(folderId?: string | null) {
  const q = folderId ? `?folder_id=${folderId}` : "";
  return api<FolderLayer>(`/folders/list${q}`);
}

export function listFolderReviewers() {
  return api<ReviewerOption[]>("/folders/reviewers");
}

export function listReviewTasks() {
  return api<ReviewTask[]>("/folders/review-tasks");
}

export function createFolder(body: {
  name: string;
  parent_id?: string | null;
  description?: string;
  visibility?: FolderVisibility;
}) {
  return api<FolderNode>("/folders", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateFolder(
  id: string,
  body: {
    name?: string;
    description?: string;
    visibility?: FolderVisibility;
  },
) {
  return api<FolderNode>(`/folders/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function renameFolder(id: string, name: string) {
  return updateFolder(id, { name });
}

export function moveFolder(id: string, parentId: string | null) {
  return api<FolderNode>(`/folders/${id}/move`, {
    method: "PATCH",
    body: JSON.stringify({ parent_id: parentId }),
  });
}

export function deleteFolder(id: string) {
  return api<void>(`/folders/${id}`, { method: "DELETE" });
}

export function moveDocumentToFolder(docId: string, folderId: string | null) {
  return api<{ ok: boolean }>(`/folders/documents/${docId}/move`, {
    method: "PATCH",
    body: JSON.stringify({ folder_id: folderId }),
  });
}

export type TenantMemberRole = "member" | "admin" | "owner";

export type TenantMember = {
  member_id: string;
  user_id: string;
  email: string;
  member_name: string;
  role: TenantMemberRole;
  active: number;
};

export type CreateMemberResult = {
  member_id: string;
  user_id: string;
  email: string;
  member_name: string;
  role: TenantMemberRole;
  temporary_password: string | null;
  must_change_password: boolean;
};

export function listTenantMembers() {
  return api<TenantMember[]>("/members");
}

export function createTenantMember(body: {
  member_name: string;
  email: string;
  role: Exclude<TenantMemberRole, "owner">;
}) {
  return api<CreateMemberResult>("/members", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function changePassword(newPassword: string) {
  return fetchBackend("/api/v1/auth/change-password", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ new_password: newPassword }),
  }).then(async (res) => {
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        if (typeof body?.detail?.message === "string") {
          detail = body.detail.message;
        } else if (typeof body?.detail === "string") {
          detail = body.detail;
        }
      } catch {
        /* ignore */
      }
      throw new Error(detail || "修改密码失败");
    }
  });
}

/* ---- F12 Embed Widget site keys (admin) ---- */

export type WidgetSiteKey = {
  id: string;
  tenant_id: string;
  public_key: string;
  status: "active" | "revoked";
  allowed_origins: string[];
  name?: string | null;
  create_at: string;
  update_at: string;
};

export type WidgetSnippet = {
  snippet: string;
  public_key: string;
};

export function listWidgetSiteKeys() {
  return api<WidgetSiteKey[]>("/admin/widget-site-keys");
}

export function createWidgetSiteKey(body: {
  allowed_origins: string[];
  name?: string;
}) {
  return api<WidgetSiteKey>("/admin/widget-site-keys", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateWidgetSiteKey(
  id: string,
  body: {
    allowed_origins?: string[];
    name?: string;
    clear_name?: boolean;
  },
) {
  return api<WidgetSiteKey>(`/admin/widget-site-keys/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function revokeWidgetSiteKey(id: string) {
  return api<WidgetSiteKey>(`/admin/widget-site-keys/${id}/revoke`, {
    method: "POST",
  });
}

export function getWidgetSnippet(id: string) {
  return api<WidgetSnippet>(`/admin/widget-site-keys/${id}/snippet`);
}

/* ---- P3-F04 Admin Debug ---- */

export type DebugSearchHit = {
  document_id: string;
  chunk_id: string;
  section_id?: string;
  path?: string;
  content: string;
  score: number;
};

export type DebugSearchResponse = {
  hits: DebugSearchHit[];
};

export type DebugLlmCall = {
  step: number;
  request_summary: Record<string, unknown>;
  response_summary: Record<string, unknown>;
};

export type AgentDebugPayload = {
  context_messages: Record<string, unknown>[];
  top_k_hits: DebugSearchHit[];
  history: Record<string, unknown>[];
  llm_calls: DebugLlmCall[];
};

export type DebugChatResponse = TurnReply & {
  debug: AgentDebugPayload;
};

export function postDebugSearch(body: { query: string; top_k?: number }) {
  return api<DebugSearchResponse>("/admin/debug/search", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function postDebugChat(body: {
  content: string;
  conversation_id?: string | null;
}) {
  return api<DebugChatResponse>("/admin/debug/chat", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
