/**
 * Production server for LAN clients.
 * Uses a capped Node heap to keep the host machine responsive.
 */
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

process.env.NODE_OPTIONS = process.env.NODE_OPTIONS || "--max-old-space-size=2048";
process.env.NEXT_TELEMETRY_DISABLED = "1";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const nextBin = path.join(root, "node_modules", "next", "dist", "bin", "next");

const child = spawn(
  process.execPath,
  [nextBin, "start", "-H", "0.0.0.0", "-p", process.env.PORT || "3001"],
  {
    stdio: "inherit",
    env: process.env,
    cwd: root,
  }
);

child.on("exit", (code) => process.exit(code ?? 0));
