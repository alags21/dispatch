import type { NextConfig } from "next";
import { resolve } from "node:path";
import { moduleBoundary } from "./scripts/module-boundary.mjs";

const frontendRoot = resolve(__dirname);
const config: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: frontendRoot,
  turbopack: { root: frontendRoot },
  poweredByHeader: false,
  webpack(config) {
    const boundary = moduleBoundary(frontendRoot);
    config.resolve.plugins = [...(config.resolve.plugins || []), boundary];
    config.resolveLoader.plugins = [...(config.resolveLoader.plugins || []), boundary];
    return config;
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.API_INTERNAL_URL || "http://127.0.0.1:8010"}/api/:path*`,
      },
    ];
  },
};
export default config;
