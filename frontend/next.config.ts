import type { NextConfig } from "next";

const staticDemoMode = process.env.NEXT_PUBLIC_SECOND_BRAIN_DEMO_MODE === "static";

const nextConfig: NextConfig = {
  turbopack: {
    root: process.cwd(),
  },
  ...(staticDemoMode
    ? {
        output: "export" as const,
        trailingSlash: true,
        images: {
          unoptimized: true,
        },
      }
    : {}),
};

export default nextConfig;
