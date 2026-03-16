import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow fetching from BCB APIs
  async headers() {
    return [
      {
        source: "/api/:path*",
        headers: [
          { key: "Cache-Control", value: "s-maxage=3600, stale-while-revalidate=7200" },
        ],
      },
    ];
  },
};

export default nextConfig;
