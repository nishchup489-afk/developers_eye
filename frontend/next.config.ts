import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow isolated verification builds alongside a running development server.
  distDir: process.env.NEXT_BUILD_DIR || ".next",
  experimental: { cpus: 2 },
  // Dev chunks keep the same URL between dev server runs, so a browser (or a service worker
  // left on this port by another project) can hand back an old copy and the page never
  // hydrates until a hard refresh. Never store them in development (INC-0038). Production
  // builds keep Next's own immutable caching for hashed chunks.
  async headers() {
    if (process.env.NODE_ENV !== "development") return [];
    return [{ source: "/_next/static/:path*", headers: [{ key: "Cache-Control", value: "no-store, must-revalidate" }] }];
  },
};

export default nextConfig;
