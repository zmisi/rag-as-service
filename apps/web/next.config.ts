import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow custom hosts (e.g. tenant-a.lxzxai.com) during `next dev`.
  allowedDevOrigins: ["tenant-a.lxzxai.com", "*.lxzxai.com", "lxzxai.com"],
  // /backend/* is proxied by app/backend/[...path]/route.ts (sets X-Forwarded-Host
  // + X-Rag-Proxy-Secret server-side). Do not use rewrites — they drop the Host.
};

export default nextConfig;
