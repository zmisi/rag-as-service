import type { NextConfig } from "next";

const apiOrigin = process.env.API_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // Allow custom hosts (e.g. tenant-a.lxzxai.com) during `next dev`.
  allowedDevOrigins: ["tenant-a.lxzxai.com", "*.lxzxai.com"],
  async rewrites() {
    return [
      {
        source: "/backend/:path*",
        destination: `${apiOrigin}/:path*`,
      },
    ];
  },
};

export default nextConfig;
