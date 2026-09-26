import type { NextConfig } from "next";

function backendApiOrigin(): string | null {
  const configured = process.env.BACKEND_API_ORIGIN?.trim();
  if (!configured) return null;

  const origin = configured.replace(/\/+$/, "");

  if (!/^https?:\/\/[^/]+$/i.test(origin)) {
    throw new Error(
      "BACKEND_API_ORIGIN must be an origin such as https://api.example.com",
    );
  }

  if (
    process.env.VERCEL_ENV === "production" &&
    !origin.startsWith("https://")
  ) {
    throw new Error("Production BACKEND_API_ORIGIN must use HTTPS.");
  }

  return origin;
}

const nextConfig: NextConfig = {
  async rewrites() {
    const origin = backendApiOrigin();
    if (!origin) return [];

    return [
      {
        source: "/api/v1",
        destination: `${origin}/api/v1`,
      },
      {
        source: "/api/v1/:path*",
        destination: `${origin}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
