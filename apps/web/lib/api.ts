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
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  meta?: Record<string, unknown> | null;
  create_at: string;
  update_at: string;
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
  const res = await fetch(`/backend/v1${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...authHeaders(),
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
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

export function listMessages(conversationId: string) {
  return api<Message[]>(`/conversations/${conversationId}/messages`);
}

export function postMessage(conversationId: string, content: string) {
  return api<Message>(`/conversations/${conversationId}/messages`, {
    method: "POST",
    body: JSON.stringify({ role: "user", content }),
  });
}
