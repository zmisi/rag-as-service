import type { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
  "host",
  "content-length",
]);

function apiOrigin(): string {
  return (
    process.env.API_BACKEND_URL ??
    process.env.API_ORIGIN ??
    "http://localhost:8000"
  ).replace(/\/$/, "");
}

function proxySecret(): string {
  return (process.env.PROXY_SHARED_SECRET ?? "").trim();
}

async function proxy(request: NextRequest, pathParts: string[]): Promise<Response> {
  const upstreamPath = "/" + pathParts.map(encodeURIComponent).join("/");
  const url = new URL(request.url);
  const target = `${apiOrigin()}${upstreamPath}${url.search}`;

  const headers = new Headers();
  request.headers.forEach((value, key) => {
    const lower = key.toLowerCase();
    if (HOP_BY_HOP.has(lower)) return;
    if (lower === "x-forwarded-host") return;
    if (lower === "x-rag-proxy-secret") return;
    headers.set(key, value);
  });

  const originalHost = request.headers.get("host") ?? "";
  headers.set("X-Forwarded-Host", originalHost);
  const secret = proxySecret();
  if (secret) {
    headers.set("X-Rag-Proxy-Secret", secret);
  }

  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: "manual",
  };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = request.body;
    Object.assign(init, { duplex: "half" });
  }

  const upstream = await fetch(target, init);
  const outHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    const lower = key.toLowerCase();
    if (HOP_BY_HOP.has(lower)) return;
    outHeaders.set(key, value);
  });

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: outHeaders,
  });
}

type RouteContext = { params: Promise<{ path: string[] }> };

async function handle(request: NextRequest, context: RouteContext): Promise<Response> {
  const { path } = await context.params;
  return proxy(request, path ?? []);
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
export const OPTIONS = handle;
export const HEAD = handle;
