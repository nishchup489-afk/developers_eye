import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow isolated verification builds alongside a running development server.
  distDir: process.env.NEXT_BUILD_DIR || ".next",
  experimental: { cpus: 2 },
};

export default nextConfig;
