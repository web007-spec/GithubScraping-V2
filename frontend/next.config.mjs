/** @type {import('next').NextConfig} */
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const apiTarget = process.env.API_PROXY_TARGET || "http://127.0.0.1:8000";
const port = process.env.PORT || "3001";
const disableHmr = process.env.DISABLE_HMR === "1";
const root = dirname(fileURLToPath(import.meta.url));
const buildCpus = Math.max(1, Number(process.env.NEXT_BUILD_CPUS || "2"));
const turboMemoryLimit = Number(process.env.TURBOPACK_MEMORY_LIMIT || 1536 * 1024 * 1024);

/** Origins allowed to load Next.js dev assets / HMR when not using localhost (LAN clients). */
function buildAllowedDevOrigins() {
  const fromEnv = (process.env.DEV_ALLOWED_ORIGINS || "")
    .split(",")
    .map((s) => s.trim().replace(/^https?:\/\//, "").replace(/\/$/, ""))
    .filter(Boolean);

  const hostPatterns = [
    "localhost",
    "127.0.0.1",
    `localhost:${port}`,
    `127.0.0.1:${port}`,
    "192.168.*",
    "10.*",
    "172.16.*",
    "172.17.*",
    "172.18.*",
    "172.19.*",
    "172.20.*",
    "172.21.*",
    "172.22.*",
    "172.23.*",
    "172.24.*",
    "172.25.*",
    "172.26.*",
    "172.27.*",
    "172.28.*",
    "172.29.*",
    "172.30.*",
    "172.31.*",
  ];

  const withPort = hostPatterns.flatMap((h) =>
    h.includes(":") ? [h] : [h, `${h}:${port}`]
  );

  return [...new Set([...withPort, ...fromEnv])];
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  allowedDevOrigins: buildAllowedDevOrigins(),
  turbopack: { root },
  cacheMaxMemorySize: 16 * 1024 * 1024,
  experimental: {
    cpus: buildCpus,
    memoryBasedWorkersCount: true,
    proxyClientMaxBodySize: "150mb",
    turbopackMemoryLimit: turboMemoryLimit,
    webpackMemoryOptimizations: true,
  },
  async rewrites() {
    return [
      {
        source: "/backend/:path*",
        destination: `${apiTarget}/:path*`,
      },
    ];
  },
  webpack: (config, { dev, isServer }) => {
    if (dev && disableHmr && !isServer) {
      config.plugins = config.plugins.filter(
        (plugin) => plugin?.constructor?.name !== "ReactRefreshWebpackPlugin"
      );
      config.optimization = {
        ...config.optimization,
        moduleIds: "named",
      };
    }
    return config;
  },
};

export default nextConfig;
