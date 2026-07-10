import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        // Route /api requests to the backend URL, completely bypassing browser Mixed Content blocks
        destination: process.env.BACKEND_URL ? `${process.env.BACKEND_URL}/:path*` : "http://localhost:8000/:path*",
      },
    ];
  },
};

export default nextConfig;
