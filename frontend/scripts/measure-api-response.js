#!/usr/bin/env node
/**
 * Measure API response times for the SaaSShadow backend.
 * Usage: node scripts/measure-api-response.js [baseUrl]
 * Default baseUrl: http://127.0.0.1:8000
 */

const BASE = process.argv[2] || "http://127.0.0.1:8000";
const ENDPOINTS = [
  { name: "GET /health", url: `${BASE}/health`, method: "GET" },
  { name: "GET /health/ready", url: `${BASE}/health/ready`, method: "GET" },
  { name: "GET /connectors", url: `${BASE}/connectors`, method: "GET" },
  { name: "GET /plugins", url: `${BASE}/plugins`, method: "GET" },
  { name: "GET /rules", url: `${BASE}/rules`, method: "GET" },
  { name: "GET /scans", url: `${BASE}/scans?limit=5`, method: "GET" },
];

async function measure(url, method = "GET") {
  const start = performance.now();
  let ok = false;
  let status = 0;
  try {
    const res = await fetch(url, { method });
    status = res.status;
    ok = res.ok;
    await res.text();
  } catch (e) {
    return { ms: null, error: e.message, ok: false, status: null };
  }
  const ms = Math.round(performance.now() - start);
  return { ms, ok, status, error: null };
}

async function main() {
  console.log("SaaSShadow API response time measurement");
  console.log("Base URL:", BASE);
  console.log("");

  for (const { name, url, method } of ENDPOINTS) {
    const result = await measure(url, method);
    if (result.error) {
      console.log(`${name}: FAILED - ${result.error}`);
    } else {
      const status = result.ok ? "OK" : `HTTP ${result.status}`;
      console.log(`${name}: ${result.ms} ms (${status})`);
    }
  }

  console.log("");
  console.log("Typical targets: /health < 100ms, /rules or /scans < 500ms.");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
