import type { NextConfig } from "next";

const apiBackendUrl =
  process.env.API_BACKEND_URL ??
  process.env.API_ORIGIN ??
  "http://localhost:8000";

const nextConfig: NextConfig = {
  // Allow custom hosts (e.g. tenant-a.lxzxai.com) during `next dev`.
  allowedDevOrigins: ["tenant-a.lxzxai.com", "*.lxzxai.com", "lxzxai.com"],
  async rewrites() {
    return [
      {
        source: "/backend/:path*",
        destination: `${apiBackendUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
