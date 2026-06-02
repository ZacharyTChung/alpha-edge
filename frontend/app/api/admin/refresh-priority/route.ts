import { NextResponse } from "next/server";

import { adminHeaders, backendAdminUrl } from "@/lib/admin-proxy";

export async function POST() {
  const response = await fetch(backendAdminUrl("/admin/refresh-priority"), {
    method: "POST",
    headers: adminHeaders(),
    cache: "no-store",
  });
  const payload = await response.json();
  return NextResponse.json(payload, { status: response.status });
}
