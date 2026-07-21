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

export type ConversationStatus = "active" | "archived";

export type Conversation = {
  id: string;
  tenant_id: string;
  user_id: string;
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
  if (typeof window !== "undefined") {
    headers["X-Forwarded-Host"] = window.location.host;
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
  conversationId: string,
  content: string,
  options?: PostMessageStreamOptions,
): Promise<TurnReply> {
  const t0 = performance.now();
  const res = await fetch(`/backend/v1/conversations/${conversationId}/messages/stream`, {
    method: "POST",
    credentials: "include",
    headers: {
      ...authHeaders(),
    },
    body: JSON.stringify({ role: "user", content }),
  });
  if (!res.ok || !res.body) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status}: ${detail}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let doneTurn: TurnReply | null = null;

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
  console.info(
    `[timing] chat.stream done conversation_id=${conversationId} ` +
      `client_total_ms=${(performance.now() - t0).toFixed(1)} ` +
      `status=${doneTurn.status} used_search=${doneTurn.used_search}`,
  );
  return doneTurn;
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
