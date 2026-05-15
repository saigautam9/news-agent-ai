import path from "node:path";
import { fileURLToPath } from "node:url";

const dir = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  // The home directory has its own lockfile; pin tracing to this project.
  outputFileTracingRoot: dir,
};

export default nextConfig;
