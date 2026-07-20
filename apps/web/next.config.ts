import type { NextConfig } from "next";

const apiBackendUrl =
  process.env.API_BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
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
