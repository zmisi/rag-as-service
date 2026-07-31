/** Host parsing for configurable multi-tenant routing (web). */

const DEFAULT_APEX_HOST = "lxzxai.com";

export const APEX_HOST =
  process.env.APEX_HOST?.trim().toLowerCase().replace(/\.$/, "") ||
  DEFAULT_APEX_HOST;

const escapedApexHost = APEX_HOST.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export const TENANT_HOST_RE = new RegExp(
  `^[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?\\.${escapedApexHost}$`,
  "i",
);

export function hostnameFromHostHeader(hostHeader: string): string {
  return hostHeader.split(":")[0].toLowerCase();
}

export function isApexHost(hostname: string): boolean {
  return hostname === APEX_HOST;
}

export function isTenantHost(hostname: string): boolean {
  return TENANT_HOST_RE.test(hostname);
}

/** Build main-site URL on the same dev port as the incoming request. */
export function buildApexUrl(
  hostHeader: string,
  pathname: string,
  protocol: string = "http:",
): string {
  const normalized = pathname.startsWith("/") ? pathname : `/${pathname}`;
  const portPart = hostHeader.includes(":")
    ? `:${hostHeader.split(":")[1]}`
    : "";
  return `${protocol}//${APEX_HOST}${portPart}${normalized}`;
}
