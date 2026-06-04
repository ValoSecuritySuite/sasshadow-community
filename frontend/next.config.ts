import type { NextConfig } from "next";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: path.join(__dirname),
  // Skip ESLint during build to speed up compilation. Run `npm run lint` in CI or pre-commit.
  eslint: { ignoreDuringBuilds: true },
  // Optional: skip TypeScript errors during build (faster, but not recommended long-term).
  // typescript: { ignoreBuildErrors: true },
};

export default nextConfig;
