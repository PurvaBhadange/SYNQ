import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  skipTrailingSlashRedirect: true,
  async rewrites() {
    const defaultBackend =
      process.env.NODE_ENV === "development"
        ? "http://localhost:8000"
        : "https://synq-6p9m.onrender.com";

    const rawBackend =
      process.env.BACKEND_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      defaultBackend;

    const backendUrl = rawBackend
      .trim()
      .replace(/[\r\n\t]+/g, "")
      .replace(/\/api\/v1\/?$/, "")
      .replace(/\/+$/, "");

    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(), payment=()",
          },
          {
            key: "Strict-Transport-Security",
            value: "max-age=63072000; includeSubDomains; preload",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
