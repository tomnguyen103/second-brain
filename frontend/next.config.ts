import type { NextConfig } from "next";
import path from "node:path";

const staticDemoMode = process.env.NEXT_PUBLIC_SECOND_BRAIN_DEMO_MODE === "static";
const frontendRoot = path.resolve(__dirname);

const nextConfig: NextConfig = {
  turbopack: {
    root: frontendRoot,
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
