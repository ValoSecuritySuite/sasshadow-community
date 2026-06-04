/**
 * API base URL configuration for SaaSShadow.ai frontend.
 * Set NEXT_PUBLIC_API_URL in .env.local (dev) or in your production environment.
 * Default is tuned for local dev with backend on 127.0.0.1:8000.
 */

/** Default API base when NEXT_PUBLIC_API_URL is not set (local dev). */
export const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

/**
 * API base URL (no trailing slash).
 * - Dev: use .env.local with NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 (or leave unset for default).
 * - Production: set NEXT_PUBLIC_API_URL to your backend URL (e.g. https://api.saasshadow.example.com).
 */
export function getApiBaseUrl(): string {
  const raw = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (raw) return raw.replace(/\/+$/, "");
  return DEFAULT_API_BASE_URL;
}
