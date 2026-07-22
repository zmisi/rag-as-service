import { NextResponse, type NextRequest } from "next/server";

import {
  buildApexUrl,
  hostnameFromHostHeader,
  isTenantHost,
} from "@/lib/hosts";

/** Paths that MUST only be served on the apex host (F01/F02). */
const APEX_ONLY_PATHS = new Set(["/register", "/login"]);

export function middleware(request: NextRequest) {
  const hostHeader = request.headers.get("host") ?? "";
  const hostname = hostnameFromHostHeader(hostHeader);
  const { pathname } = request.nextUrl;

  if (
    isTenantHost(hostname) &&
    APEX_ONLY_PATHS.has(pathname)
  ) {
    const target = buildApexUrl(
      hostHeader,
      pathname,
      request.nextUrl.protocol,
    );
    return NextResponse.redirect(new URL(target));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/register", "/login"],
};
