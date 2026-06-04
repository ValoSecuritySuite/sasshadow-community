#!/usr/bin/env node
/**
 * Measure frontend (Next.js) response times for key routes.
 * Start the dev server first: npm run dev (or npm run dev:turbo)
 * Usage: node scripts/measure-frontend-response.js [baseUrl]
 * Default baseUrl: http://127.0.0.1:3000
 */

const BASE = process.argv[2] || "http://127.0.0.1:3000";
const ROUTES = [
  { name: "GET / (home)", path: "/" },
  { name: "GET /dashboard", path: "/dashboard" },
  { name: "GET /scan", path: "/scan" },
  { name: "GET /connectors", path: "/connectors" },
  { name: "GET /health", path: "/health" },
  { name: "GET /rules", path: "/rules" },
  { name: "GET /plugins", path: "/plugins" },
  { name: "GET /reports", path: "/reports" },
  { name: "GET /settings", path: "/settings" },
];

async function measure(url) {
  const start = performance.now();
  let ok = false;
  let status = 0;
  let size = 0;
  try {
    const res = await fetch(url, {
      method: "GET",
      headers: { Accept: "text/html" },
      redirect: "follow",
    });
    status = res.status;
    ok = res.ok;
    const text = await res.text();
    size = text.length;
  } catch (e) {
    return { ms: null, error: e.message, ok: false, status: null, size: 0 };
  }
  const ms = Math.round(performance.now() - start);
  return { ms, ok, status, error: null, size };
}

async function main() {
  console.log("SaaSShadow frontend response time measurement");
  console.log("Base URL:", BASE);
  console.log("(Start dev server first: npm run dev or npm run dev:turbo)");
  console.log("");

  const results = [];
  for (const { name, path } of ROUTES) {
    const url = `${BASE}${path}`;
    const result = await measure(url);
    results.push({ name, path, url, ...result });
    if (result.error) {
      console.log(`${name}: FAILED - ${result.error}`);
    } else {
      const status = result.ok ? "OK" : `HTTP ${result.status}`;
      const sizeK = result.size ? ` ${(result.size / 1024).toFixed(1)} KB` : "";
      console.log(`${name}: ${result.ms} ms (${status})${sizeK}`);
    }
  }

  const succeeded = results.filter((r) => r.ms != null);
  if (succeeded.length > 0) {
    const avg = Math.round(
      succeeded.reduce((s, r) => s + r.ms, 0) / succeeded.length
    );
    const min = Math.min(...succeeded.map((r) => r.ms));
    const max = Math.max(...succeeded.map((r) => r.ms));
    console.log("");
    console.log("Summary: avg", avg, "ms | min", min, "ms | max", max, "ms");
  }

  console.log("");
  console.log(
    "Targets: first load 200–800ms (dev), < 300ms (prod). Cold routes can be 1–3s in dev."
  );
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
