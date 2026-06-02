const BACKEND_API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
const ADMIN_API_KEY = process.env.ADMIN_API_KEY;

export function adminHeaders(): HeadersInit {
  return ADMIN_API_KEY ? { "X-Admin-Token": ADMIN_API_KEY } : {};
}

export function backendAdminUrl(path: string): string {
  return `${BACKEND_API_BASE}${path}`;
}
