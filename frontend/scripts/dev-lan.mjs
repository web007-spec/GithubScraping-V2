/**
 * Dev server for LAN clients (other PCs on http://YOUR_IP:3001).
 * Uses webpack/no HMR and a capped Node heap to reduce local computer load.
 */
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

process.env.DISABLE_HMR = "1";
process.env.NODE_OPTIONS = process.env.NODE_OPTIONS || "--max-old-space-size=2048";
process.env.NEXT_TELEMETRY_DISABLED = "1";
process.env.NEXT_BUILD_CPUS = process.env.NEXT_BUILD_CPUS || "2";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const nextBin = path.join(root, "node_modules", "next", "dist", "bin", "next");

const child = spawn(
  process.execPath,
  [nextBin, "dev", "--webpack", "-H", "0.0.0.0", "-p", process.env.PORT || "3001"],
  {
    stdio: "inherit",
    env: process.env,
    cwd: root,
  }
);

child.on("exit", (code) => process.exit(code ?? 0));
