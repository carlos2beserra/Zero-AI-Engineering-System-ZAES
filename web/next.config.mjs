import { createMDX } from "fumadocs-mdx/next";

const withMDX = createMDX();

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  reactStrictMode: true,
  pageExtensions: ["ts", "tsx", "md", "mdx"],
  images: { unoptimized: true },
};

const config = withMDX(nextConfig);

// fumadocs-mdx sets experimental.turbo which is deprecated in Next.js 15.
// Move it to the top-level turbopack key. NOSONAR: intentional migration away from the deprecated key.
if (config.experimental?.turbo) { // NOSONAR javascript:S1874
  config.turbopack = { ...config.turbopack, ...config.experimental.turbo }; // NOSONAR javascript:S1874
  delete config.experimental.turbo; // NOSONAR javascript:S1874
}

export default config;
