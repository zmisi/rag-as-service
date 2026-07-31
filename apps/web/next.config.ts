import type { NextConfig } from "next";

const apexHost = process.env.APEX_HOST?.trim() || "lxzxai.com";

const nextConfig: NextConfig = {
  output: "standalone",
  // Allow the configured apex and tenant hosts during `next dev`.
  allowedDevOrigins: [apexHost, `*.${apexHost}`],
  // /backend/* is proxied by app/backend/[...path]/route.ts (sets X-Forwarded-Host
  // + X-Rag-Proxy-Secret server-side). Do not use rewrites — they drop the Host.
};

export default nextConfig;
