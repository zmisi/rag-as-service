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

export async function fetchBackend(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  return fetch(backendUrl(path), {
    ...init,
    credentials: "include",
  });
}
