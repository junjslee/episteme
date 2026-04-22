import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,

  // Vercel defaults. Kept explicit so rollbacks / alt-host deploys are legible.
  // The Node.js runtime is required by the three API route handlers in
  // src/app/api/{chain,protocols,surface}/route.ts which call fs.readFile.
  // Do NOT move those routes to edge without first replacing fs with an
  // HTTP-based data fetch.

  experimental: {
    // Tighten the Server Actions body limit. We don't ship any Server Actions
    // today; this prevents accidental future blobs from slipping in silently.
    serverActions: {
      bodySizeLimit: "1mb",
    },
  },
};

export default nextConfig;
